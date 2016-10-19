from django.db import models

class Grading(models.Model):
    title = models.CharField(max_length=20, help_text="The title of the grade, such as 'A', 'B', 'Pass', or 'Fail'.")
    means_passed = models.BooleanField(default=True, help_text="Students are informed about their pass or fail in the assignment, based on this flag in their given grade.")

    class Meta:
        app_label = 'opensubmit'
        ordering = ['title']

    def __unicode__(self):
        return unicode(self.title)

    def means_failed(self):
    	return not self.means_passed
