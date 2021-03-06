# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-04-13 13:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0010_auto_20160413_1224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='lti_key',
            field=models.CharField(blank=True, help_text=b'Key to be used by an LTI consumer when accessing this course.', max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='lti_secret',
            field=models.CharField(blank=True, help_text=b'Secret to be used by an LTI consumer when accessing this course.', max_length=100, null=True),
        ),
    ]
