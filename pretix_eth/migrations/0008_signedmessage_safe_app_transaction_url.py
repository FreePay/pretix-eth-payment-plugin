# Generated by Django 3.2.16 on 2023-06-06 16:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pretix_eth', '0007_signedmessage_is_confirmed'),
    ]

    operations = [
        migrations.AddField(
            model_name='signedmessage',
            name='safe_app_transaction_url',
            field=models.TextField(null=True),
        ),
    ]