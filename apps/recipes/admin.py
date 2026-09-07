from django.contrib import admin
from .models import Menu, MenuItem, RecipeContext, Recipe, RecipeIngredient


@admin.register(RecipeContext)
class RecipeContextAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'target_fc_pct')
    list_filter = ('organization',)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    readonly_fields = ('get_cost_display',)

    def get_cost_display(self, obj):
        return f'{obj.get_cost():.4f} PLN'
    get_cost_display.short_description = 'Koszt'


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'meal_type', 'yield_portions', 'selling_price', 'manual_cost_override')
    list_filter = ('organization', 'meal_type')
    search_fields = ('name',)
    inlines = [RecipeIngredientInline]


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    readonly_fields = ('get_cost_display',)

    def get_cost_display(self, obj):
        return f'{obj.get_cost():.2f} PLN'
    get_cost_display.short_description = 'Koszt'


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'package_price_per_person', 'target_fc_pct')
    list_filter = ('organization',)
    search_fields = ('name',)
    inlines = [MenuItemInline]
