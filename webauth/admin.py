from django.contrib import admin
from webauth.models import AdminMember, ManagerMember, ModeratorMember


# Register your models here.

@admin.register(AdminMember)
class AdminMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('created_at', 'updated_at')


@admin.register(ManagerMember)
class ManagerMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('created_at', 'updated_at')


@admin.register(ModeratorMember)
class ModeratorMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('created_at', 'updated_at')
