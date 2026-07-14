from datetime import date

from django.utils import timezone

from .models import BirthdayCelebration, Pet


BIRTHDAY_POPUP_WINDOW_DAYS = 3
BIRTHDAY_FRAME_DAYS = 7


def birthday_for_year(birth_date, year):
    """Devuelve el cumpleaños del año; 29/2 pasa al 28/2 en años no bisiestos."""
    try:
        return date(year, birth_date.month, birth_date.day)
    except ValueError:
        return date(year, 2, 28)


def badge_for_age(age):
    if age <= 1:
        return {
            'code': 'first-birthday',
            'emoji': '🌟',
            'name': 'Mi primer cumpleaños',
            'subtitle': 'El comienzo de una vida llena de aventuras',
        }
    if age == 5:
        return {
            'code': 'five-years',
            'emoji': '🏅',
            'name': 'Cinco años juntos',
            'subtitle': 'Cinco años de amor, juegos y recuerdos',
        }
    if age >= 10:
        return {
            'code': 'legend',
            'emoji': '👑',
            'name': 'Leyenda VetPaw',
            'subtitle': 'Una historia enorme de amor y compañía',
        }
    return {
        'code': f'birthday-{age}',
        'emoji': '🎖️',
        'name': f'Cumpleañero VetPaw · {age} años',
        'subtitle': 'Un año más llenando de alegría su hogar',
    }


def birthday_message(pet, age):
    species = (pet.species or '').lower()
    phrases = {
        'dog': 'años de paseos, juegos, patitas y amor incondicional',
        'cat': 'años de ronroneos, siestas, travesuras y mucho amor',
        'horse': 'años de nobleza, aventuras y momentos inolvidables',
        'rabbit': 'años de saltitos, ternura y compañía',
        'bird': 'años llenando el hogar de color, compañía y alegría',
        'fish': 'años aportando calma, color y compañía',
        'hamster': 'años de pequeñas aventuras y enorme ternura',
        'reptile': 'años de compañía única y recuerdos especiales',
        'cow': 'años de nobleza, ternura y hermosos momentos',
    }
    phrase = phrases.get(species, 'años de aventuras, compañía y muchísimo amor')
    return f'{pet.name} cumple {age} año{"s" if age != 1 else ""}: {phrase}. ¡Feliz cumpleaños de parte de toda la comunidad VetPaw!'


def gift_for_pet(pet):
    species = (pet.species or '').lower()
    if species == 'dog':
        return 'Vale por un paseo especial, una sesión extra de juegos y todos los mimos que quiera.'
    if species == 'cat':
        return 'Vale por una tarde de juegos, una siesta sin interrupciones y mimos a su manera.'
    if species == 'horse':
        return 'Vale por una jornada tranquila, cepillado con cariño y un momento especial juntos.'
    return 'Vale por un momento especial de juegos, compañía y muchos mimos adaptados a su especie.'


def sync_birthday_celebrations(user, today=None):
    """Crea el recuerdo del año al primer ingreso posterior al cumpleaños.

    No necesita cron, correo ni servicios pagos: se ejecuta al consultar la API.
    """
    today = today or timezone.localdate()
    if not getattr(user, 'is_owner', False):
        return []

    created = []
    pets = Pet.objects.filter(owner=user, birth_date__isnull=False)
    for pet in pets:
        birthday = birthday_for_year(pet.birth_date, today.year)
        age = today.year - pet.birth_date.year
        if age < 1 or birthday > today:
            continue
        celebration, was_created = BirthdayCelebration.objects.get_or_create(
            pet=pet,
            year=today.year,
            defaults={
                'age': age,
                'birthday_date': birthday,
            },
        )
        if was_created:
            created.append(celebration)
    return created
