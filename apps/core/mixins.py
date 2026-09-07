class TenantQuerySetMixin:
    """
    Filtruje queryset do danych bieżącej organizacji.
    Guard na organization=None zapobiega wyciekowi danych przy niekompletnym onboardingu.
    """

    def get_queryset(self):
        if not self.request.user.organization_id:
            return super().get_queryset().none()
        return super().get_queryset().filter(
            organization=self.request.user.organization
        )
