from rest_framework.pagination import PageNumberPagination as _Base


class PageNumberPagination(_Base):
    page_size_query_param = 'page_size'
    max_page_size = 200
