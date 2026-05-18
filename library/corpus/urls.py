from django.urls import path

from corpus import views

urlpatterns = [
    path("health", views.health_view, name="api-health"),
    path("search", views.search_api, name="api-search"),
    path("recommendations/query", views.recommendations_query_view),
    path("index/stats", views.index_stats_view),
    path("catalog/popular", views.popular_books_view),
    path("catalog/classics", views.classic_books_view),
    path("ai/explain", views.ai_explain_view),
    path("ai/chat", views.ai_chat_view),
]
