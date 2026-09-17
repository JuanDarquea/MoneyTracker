class Category {
  Category({
    required this.id,
    required this.name,
    required this.type,
    required this.isArchived,
  });

  final String id;
  final String name;
  final String type;
  final bool isArchived;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        type: json['type'] as String,
        isArchived: json['is_archived'] as bool,
      );
}
