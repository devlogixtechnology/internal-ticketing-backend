from rest_framework import serializers
from .models import Ticket, TicketHistory, Category
from apps.accounts.models import CustomUser

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class TicketSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        source='category', 
        write_only=True
    )
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ['id', 'title', 'description', 'category', 'category_id', 'priority', 'status', 'created_by', 'assigned_to', 'created_at']
        read_only_fields = ['id', 'status', 'created_by', 'assigned_to', 'created_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class AssignTicketSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)

    def validate_user_id(self, value):
        if not CustomUser.objects.filter(id=value, role='SUPPORT').exists():
            raise serializers.ValidationError("User with this ID does not exist or is not a Support Agent.")
        return value


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=20, required=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')