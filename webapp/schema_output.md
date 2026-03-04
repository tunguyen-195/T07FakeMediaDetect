## CHI TIẾT CẤU TRÚC CÁC BẢNG (SCHEMA)

Dưới đây là danh sách chi tiết các cột trong từng bảng của database hiện tại:

### 🔹 Bảng: `django_migrations`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **app** | varchar(255) | Không |  |  |
| **name** | varchar(255) | Không |  |  |
| **applied** | datetime | Không |  |  |

### 🔹 Bảng: `sqlite_sequence`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **name** |  | Có |  |  |
| **seq** |  | Có |  |  |

### 🔹 Bảng: `auth_group_permissions`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **group_id** | INTEGER | Không |  |  |
| **permission_id** | INTEGER | Không |  |  |

### 🔹 Bảng: `auth_user_groups`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **user_id** | INTEGER | Không |  |  |
| **group_id** | INTEGER | Không |  |  |

### 🔹 Bảng: `auth_user_user_permissions`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **user_id** | INTEGER | Không |  |  |
| **permission_id** | INTEGER | Không |  |  |

### 🔹 Bảng: `django_admin_log`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **action_time** | datetime | Không |  |  |
| **object_id** | TEXT | Có |  |  |
| **object_repr** | varchar(200) | Không |  |  |
| **change_message** | TEXT | Không |  |  |
| **content_type_id** | INTEGER | Có |  |  |
| **user_id** | INTEGER | Không |  |  |
| **action_flag** | smallint unsigned | Không |  |  |

### 🔹 Bảng: `django_content_type`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **app_label** | varchar(100) | Không |  |  |
| **model** | varchar(100) | Không |  |  |

### 🔹 Bảng: `auth_permission`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **content_type_id** | INTEGER | Không |  |  |
| **codename** | varchar(100) | Không |  |  |
| **name** | varchar(255) | Không |  |  |

### 🔹 Bảng: `auth_group`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **name** | varchar(150) | Không |  |  |

### 🔹 Bảng: `auth_user`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **id** | INTEGER | Không |  | ✓ |
| **password** | varchar(128) | Không |  |  |
| **last_login** | datetime | Có |  |  |
| **is_superuser** | bool | Không |  |  |
| **username** | varchar(150) | Không |  |  |
| **last_name** | varchar(150) | Không |  |  |
| **email** | varchar(254) | Không |  |  |
| **is_staff** | bool | Không |  |  |
| **is_active** | bool | Không |  |  |
| **date_joined** | datetime | Không |  |  |
| **first_name** | varchar(150) | Không |  |  |

### 🔹 Bảng: `django_session`
| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |
| :--- | :--- | :--- | :--- | :--- |
| **session_key** | varchar(40) | Không |  | ✓ |
| **session_data** | TEXT | Không |  |  |
| **expire_date** | datetime | Không |  |  |

