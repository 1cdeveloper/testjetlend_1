from django.conf import settings
from django.db import models
from django.utils import timezone


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    discount_percent = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    max_usage_count = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def usage_count(self) -> int:
        return self.orders.count()


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2)
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} by {self.user_id}"
