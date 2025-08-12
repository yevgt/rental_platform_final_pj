import pytest
from datetime import date, timedelta
from properties.models import Property
from bookings.models import Booking
from notifications.models import Notification

@pytest.mark.django_db
def test_notifications_on_booking_flow(user_factory):
    # Создаём арендодателя и арендатора
    landlord = user_factory("landlord@example.com", role="landlord", name="Owner")
    renter = user_factory("renter@example.com", role="renter", name="Renter")

    # Создаём объект недвижимости
    prop = Property.objects.create(
        title="Квартира",
        description="Центр",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active",
    )

    # 1) Создание бронирования -> уведомление арендодателю о новой заявке
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        # В вашей БД monthly_rent NOT NULL — подаём значения
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )
    notif_landlord = Notification.objects.filter(user=landlord, type=Notification.Types.BOOKING_NEW)
    assert notif_landlord.exists()

    # 2) Подтверждение -> уведомление арендатору
    booking.status = Booking.Status.CONFIRMED
    booking.save(update_fields=["status"])
    notif_renter_conf = Notification.objects.filter(user=renter, type=Notification.Types.BOOKING_CONFIRMED)
    assert notif_renter_conf.exists()

    # 3) Отклонение -> уведомление арендатору
    booking.status = Booking.Status.REJECTED
    booking.save(update_fields=["status"])
    notif_renter_rej = Notification.objects.filter(user=renter, type=Notification.Types.BOOKING_REJECTED)
    assert notif_renter_rej.exists()