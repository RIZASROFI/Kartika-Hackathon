from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("intel", "0004_alter_contentitem_source_type"),
    ]

    operations = [
        migrations.DeleteModel(name="CoordinationLink"),
    ]
