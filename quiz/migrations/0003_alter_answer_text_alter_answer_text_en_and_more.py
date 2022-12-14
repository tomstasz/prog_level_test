# Generated by Django 4.0.8 on 2022-12-21 10:28

import ckeditor.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0002_quiz_number_of_junior_series_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answer',
            name='text',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='answer',
            name='text_en',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='answer',
            name='text_pl',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='text',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='text_en',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='text_pl',
            field=ckeditor.fields.RichTextField(blank=True, null=True),
        ),
    ]
