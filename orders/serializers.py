from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Order, PromoCode


User = get_user_model()


class OrderCreateSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    promo_code = serializers.CharField(required=False, allow_blank=False)

    def validate_promo_code(self, value: str) -> str:
        try:
            promo = PromoCode.objects.get(code=value)
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError("Invalid promo code.")

        if promo.is_expired:
            raise serializers.ValidationError("Promo code has expired.")

        if promo.usage_count >= promo.max_usage_count:
            raise serializers.ValidationError("Promo code usage limit exceeded.")

        user = self.initial_data.get("user_id")
        if user is not None:
            if Order.objects.filter(user_id=user, promo_code=promo).exists():
                raise serializers.ValidationError("Promo code already used by this user.")

        self.context["promo_instance"] = promo
        return value

    def create(self, validated_data):
        user = validated_data["user"]
        amount: Decimal = validated_data["amount"]
        promo_instance: PromoCode | None = self.context.get("promo_instance")

        discount_amount = Decimal("0.00")
        final_amount = amount

        if promo_instance:
            discount_percent = Decimal(promo_instance.discount_percent) / Decimal("100")
            discount_amount = (amount * discount_percent).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            final_amount = amount - discount_amount

        order = Order.objects.create(
            user=user,
            amount=amount,
            final_amount=final_amount,
            promo_code=promo_instance,
        )

        return order


class OrderResponseSerializer(serializers.ModelSerializer):
    promo_code = serializers.CharField(source="promo_code.code", allow_null=True)

    class Meta:
        model = Order
        fields = ["id", "user_id", "amount", "final_amount", "promo_code", "created_at"]

