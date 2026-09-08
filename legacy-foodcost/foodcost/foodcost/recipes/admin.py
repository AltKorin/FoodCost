from django.contrib import admin
from .models import Recipe, RecipeIngredient, RecipeContext


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 3
    fields = ['ingredient', 'quantity', 'unit', 'yield_factor', 'is_optional', 'notes']
    autocomplete_fields = ['ingredient']


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['name', 'meal_type', 'get_contexts', 'cost_per_portion_display',
                    'selling_price', 'food_cost_percentage', 'is_active']
    list_filter = ['meal_type', 'contexts', 'is_active']
    search_fields = ['name']
    inlines = [RecipeIngredientInline]
    filter_horizontal = ['contexts']

    @admin.display(description='Konteksty')
    def get_contexts(self, obj):
        return ', '.join(c.get_context_display() for c in obj.contexts.all())

    @admin.display(description='Koszt/porcja')
    def cost_per_portion_display(self, obj):
        cpp = obj.cost_per_portion
        return f'{cpp} PLN' if cpp else '—'

    @admin.display(description='FC%')
    def food_cost_percentage(self, obj):
        fc = obj.food_cost_percentage
        return f'{fc}%' if fc else '—'


@admin.register(RecipeContext)
class RecipeContextAdmin(admin.ModelAdmin):
    list_display = ['get_context_display', 'target_fc_percentage']

    def get_context_display(self, obj):
        return obj.get_context_display()
    get_context_display.short_description = 'Kontekst'
