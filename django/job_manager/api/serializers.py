from job_manager.job import Job, Status, Task
from rest_framework import serializers


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ('state', 'date', 'description' )

class TaskSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField()

    class Meta:
        model = Task
        fields = ('pk','complete',)

class JobSerializer(serializers.HyperlinkedModelSerializer):
    status_set = StatusSerializer(many=True)
    task_set = TaskSerializer(many=True)

    class Meta:
        model = Job
        fields = ('pk', 'date_created','submission_id', 'remote_results_path', 'results_file', 'task_set',  'status_set')

    def create(self, validated_data):
        status_data = validated_data.pop('status_set')
        job = Job.objects.create(**validated_data)
        job.save()
        for status in status_data:
            Status.objects.create(job = job, **status_data)
        return job

    def update(self, job, validated_data):
        if 'submission_id' in validated_data.keys():
            job.submission_id = validated_data['submission_id']

        if 'remote_results_path' in validated_data.keys():
            job.remote_results_path = validated_data['remote_results_path']

        status_data = validated_data.get('status_set',None)
        if(status_data):
            for status in status_data:
                Status.objects.create(job = job, **status)

        task_list = validated_data.get('task_set',None)
        if(task_list):
            for task_data in task_list:
                task = job.task_set.get(pk=task_data['pk'])
                if(task.complete == False and task_data['complete'] == True):
                    task.finish()

        job.save()
        return job
