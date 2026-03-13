from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import Order, PromoCode


User = get_user_model()


class OrderCreateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="user1", password="testpass")
        self.url = reverse("order-create")

    def _create_promo(
        self,
        code: str = "PROMO",
        discount_percent: int = 10,
        expires_in_days: int = 1,
        max_usage_count: int = 5,
    ) -> PromoCode:
        return PromoCode.objects.create(
            code=code,
            discount_percent=discount_percent,
            expires_at=timezone.now() + timedelta(days=expires_in_days),
            max_usage_count=max_usage_count,
        )

    def test_create_order_without_promo(self):
        payload = {"user_id": self.user.id, "amount": "1000.00"}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.amount, Decimal("1000.00"))
        self.assertEqual(order.final_amount, Decimal("1000.00"))
        self.assertIsNone(order.promo_code)
        self.assertEqual(response.data["amount"], "1000.00")
        self.assertEqual(response.data["final_amount"], "1000.00")
        self.assertIsNone(response.data["promo_code"])

    def test_create_order_with_valid_promo(self):
        promo = self._create_promo(code="SUMMER2025", discount_percent=10)
        payload = {"user_id": self.user.id, "amount": "1000.00", "promo_code": promo.code}

        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.final_amount, Decimal("900.00"))
        self.assertEqual(order.promo_code, promo)
        self.assertEqual(response.data["promo_code"], promo.code)
        self.assertEqual(response.data["final_amount"], "900.00")

    def test_discount_rounding_half_up(self):
        # 10% от 100.05 = 10.005 -> 10.01 
        promo = self._create_promo(code="ROUND", discount_percent=10)
        payload = {"user_id": self.user.id, "amount": "100.05", "promo_code": promo.code}

        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.final_amount, Decimal("90.04"))
        self.assertEqual(response.data["final_amount"], "90.04")

    def test_invalid_promo_code(self):
        payload = {"user_id": self.user.id, "amount": "1000.00", "promo_code": "UNKNOWN"}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("promo_code", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_expired_promo_code(self):
        promo = PromoCode.objects.create(
            code="OLD",
            discount_percent=10,
            expires_at=timezone.now() - timedelta(days=1),
            max_usage_count=5,
        )
        payload = {"user_id": self.user.id, "amount": "1000.00", "promo_code": promo.code}

        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("promo_code", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_promo_code_usage_limit_exceeded(self):
        promo = self._create_promo(code="LIMITED", max_usage_count=1)
        other_user = User.objects.create_user(username="user2", password="testpass")
        Order.objects.create(
            user=other_user,
            amount=Decimal("100.00"),
            final_amount=Decimal("90.00"),
            promo_code=promo,
        )

        payload = {"user_id": self.user.id, "amount": "1000.00", "promo_code": promo.code}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("promo_code", response.data)
        self.assertEqual(Order.objects.filter(promo_code=promo).count(), 1)

    def test_same_user_cannot_use_promo_twice(self):
        promo = self._create_promo(code="ONCE", max_usage_count=5)
        Order.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            final_amount=Decimal("90.00"),
            promo_code=promo,
        )

        payload = {"user_id": self.user.id, "amount": "1000.00", "promo_code": promo.code}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("promo_code", response.data)
        self.assertEqual(Order.objects.filter(user=self.user, promo_code=promo).count(), 1)

    def test_promo_can_be_used_by_different_users_until_limit(self):
        promo = self._create_promo(code="MULTI", max_usage_count=2)
        other_user = User.objects.create_user(username="user2", password="testpass")

        for u in (self.user, other_user):
            payload = {"user_id": u.id, "amount": "200.00", "promo_code": promo.code}
            response = self.client.post(self.url, data=payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        #третья попытка должна упасть по лимиту
        third_user = User.objects.create_user(username="user3", password="testpass")
        payload = {"user_id": third_user.id, "amount": "200.00", "promo_code": promo.code}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("promo_code", response.data)
        self.assertEqual(Order.objects.filter(promo_code=promo).count(), 2)

    def test_missing_required_fields(self):
        #отсутствует amount
        payload = {"user_id": self.user.id}
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

        #отсутствует user_id
        payload = {"amount": "100.00"}
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_id", response.data)

    def test_invalid_amount_format(self):
        payload = {"user_id": self.user.id, "amount": "not-a-number"}
        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

