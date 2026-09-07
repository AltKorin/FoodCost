from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, LoginEvent


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'plan', 'accepted_tos_at', 'created_at')
    list_filter = ('plan',)
    search_fields = ('name', 'slug')
    readonly_fields = ('created_at',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'organization', 'role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active', 'organization')
    search_fields = ('email', 'username', 'organization__name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('FoodCost', {'fields': ('organization', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('FoodCost', {'fields': ('organization', 'role')}),
    )


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'username_attempted', 'user', 'ip_address', 'timestamp')
    list_filter = ('event_type',)
    search_fields = ('username_attempted', 'ip_address')
    readonly_fields = ('event_type', 'user', 'username_attempted', 'ip_address', 'user_agent', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
