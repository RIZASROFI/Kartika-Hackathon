from django.core.management.base import BaseCommand

from intel.services.seed_service import seed_demo_data


class Command(BaseCommand):
    help = "Isi database dengan 14 analisis demo sintetis (hanya bila kosong)."

    def handle(self, *args, **options):
        created = seed_demo_data()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"{created} analisis demo berhasil dimuat.")
            )
        else:
            self.stdout.write(
                self.style.WARNING("Data sudah ada; seed dilewati.")
            )
