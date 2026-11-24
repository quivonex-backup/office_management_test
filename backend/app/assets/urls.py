from django.urls import path

from .views import (
    AssetAssignAPIView,
    AssetCategoryCreateAPIView,
    AssetCategoryDeactivateAPIView,
    AssetCategoryListAPIView,
    AssetCategoryUpdateAPIView,
    AssetCreateAPIView,
    AssetDeactivateAPIView,
    AssetDetailAPIView,
    AssetListAPIView,
    AssetReturnAPIView,
    AssetUpdateAPIView,
    MyAssetListAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Categories
    path("category/create/", AssetCategoryCreateAPIView.as_view(), name="asset-category-create"),              #A  perm: asset.manage
    path("category/list/", AssetCategoryListAPIView.as_view(), name="asset-category-list"),                    #A  perm: asset.manage, asset.view (any)
    path("category/update/", AssetCategoryUpdateAPIView.as_view(), name="asset-category-update"),              #A  perm: asset.manage
    path("category/deactivate/", AssetCategoryDeactivateAPIView.as_view(), name="asset-category-deactivate"),  #A  perm: asset.manage

    # Assets
    path("asset/create/", AssetCreateAPIView.as_view(), name="asset-create"),                                  #A  perm: asset.manage
    path("asset/list/", AssetListAPIView.as_view(), name="asset-list"),                                        #A  perm: asset.manage, asset.view (any)
    path("asset/detail/", AssetDetailAPIView.as_view(), name="asset-detail"),                                  #A  perm: asset.manage, asset.view (any)
    path("asset/update/", AssetUpdateAPIView.as_view(), name="asset-update"),                                  #A  perm: asset.manage
    path("asset/assign/", AssetAssignAPIView.as_view(), name="asset-assign"),                                  #A  perm: asset.manage
    path("asset/return/", AssetReturnAPIView.as_view(), name="asset-return"),                                  #A  perm: asset.manage
    path("asset/deactivate/", AssetDeactivateAPIView.as_view(), name="asset-deactivate"),                      #A  perm: asset.manage
    path("asset/my-assets/", MyAssetListAPIView.as_view(), name="asset-my-assets"),                            #E  any employee
]
