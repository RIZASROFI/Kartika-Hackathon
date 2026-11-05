from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intel", "0007_remove_bot_ai_signals"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysis",
            name="decision",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
