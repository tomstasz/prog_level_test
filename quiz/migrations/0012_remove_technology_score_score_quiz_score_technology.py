# Generated by Django 4.0.8 on 2023-01-12 11:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0011_score_remove_quiz_general_score_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='technology',
            name='score',
        ),
        migrations.AddField(
            model_name='score',
            name='quiz',
            field=models.ForeignKey(default=129, on_delete=django.db.models.deletion.CASCADE, to='quiz.quiz'),
        ),
        migrations.AddField(
            model_name='score',
            name='technology',
            field=models.OneToOneField(default=2, on_delete=django.db.models.deletion.CASCADE, to='quiz.technology'),
        ),
    ]
