from django.db import migrations

REMOVED_CATEGORIES = ("bot_ai",)


def remove_signals(apps, schema_editor):
    AnalysisSignal = apps.get_model("intel", "AnalysisSignal")
    AnalysisSignal.objects.filter(category__in=REMOVED_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("intel", "0006_remove_provocation_coordination_signals"),
    ]

    operations = [
        migrations.RunPython(remove_signals, migrations.RunPython.noop),
    ]
