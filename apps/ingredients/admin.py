from django.contrib import admin
from .models import Category, Supplier, Ingredient, SupplierPrice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'order')
    list_filter = ('organization',)
    search_fields = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'phone', 'email')
    list_filter = ('organization',)
    search_fields = ('name', 'contact_name')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'category', 'base_unit', 'is_active')
    list_filter = ('organization', 'category', 'base_unit', 'is_active')
    search_fields = ('name',)


@admin.register(SupplierPrice)
class SupplierPriceAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'supplier', 'price', 'unit', 'price_per_base_unit', 'is_current', 'valid_from')
    list_filter = ('is_current', 'supplier')
    search_fields = ('ingredient__name', 'supplier__name')
    readonly_fields = ('price_per_base_unit', 'is_current', 'valid_from')
