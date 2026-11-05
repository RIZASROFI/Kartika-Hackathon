from django.db import migrations

REMOVED_CATEGORIES = ("provocation", "coordination")
REMOVED_VERDICTS = ("terkoordinasi", "provokatif")


def remove_signals(apps, schema_editor):
    AnalysisSignal = apps.get_model("intel", "AnalysisSignal")
    Analysis = apps.get_model("intel", "Analysis")

    AnalysisSignal.objects.filter(category__in=REMOVED_CATEGORIES).delete()
    Analysis.objects.filter(verdict__in=REMOVED_VERDICTS).update(
        verdict="perlu_verifikasi"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("intel", "0005_delete_coordinationlink"),
    ]

    operations = [
        migrations.RunPython(remove_signals, migrations.RunPython.noop),
    ]
