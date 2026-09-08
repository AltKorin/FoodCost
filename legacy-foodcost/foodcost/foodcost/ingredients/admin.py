from django.contrib import admin
from .models import Category, Ingredient, Supplier, SupplierPrice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']
    ordering = ['order', 'name']


class SupplierPriceInline(admin.TabularInline):
    model = SupplierPrice
    extra = 1
    fields = ['supplier', 'price', 'unit', 'package_size', 'is_current', 'source_note']
    readonly_fields = ['price_per_base_unit', 'valid_from']


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'base_unit', 'get_best_price_display', 'is_active']
    list_filter = ['category', 'is_active', 'base_unit']
    search_fields = ['name']
    inlines = [SupplierPriceInline]

    @admin.display(description='Najlepsza cena')
    def get_best_price_display(self, obj):
        p = obj.get_current_best_price()
        if p:
            return f'{p.price_per_base_unit} PLN/{obj.base_unit} ({p.supplier})'
        return '—'


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'phone', 'delivery_days', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(SupplierPrice)
class SupplierPriceAdmin(admin.ModelAdmin):
    list_display = ['ingredient', 'supplier', 'price', 'unit', 'price_per_base_unit', 'valid_from', 'is_current']
    list_filter = ['supplier', 'is_current']
    search_fields = ['ingredient__name']
    readonly_fields = ['price_per_base_unit', 'valid_from']
