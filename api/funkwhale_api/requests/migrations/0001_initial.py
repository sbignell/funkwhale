# Generated by Django 2.0.2 on 2018-02-20 22:49

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('imported_date', models.DateTimeField(blank=True, null=True)),
                ('artist_name', models.CharField(max_length=250)),
                ('albums', models.CharField(blank=True, max_length=3000, null=True)),
                ('status', models.CharField(choices=[('pending', 'pending'), ('accepted', 'accepted'), ('imported', 'imported'), ('closed', 'closed')], default='pending', max_length=50)),
                ('comment', models.TextField(blank=True, max_length=3000, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='import_requests', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
