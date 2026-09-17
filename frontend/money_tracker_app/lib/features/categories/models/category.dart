class Category {
  Category({
    required this.id,
    required this.name,
    required this.type,
    required this.isEssential,
    required this.isArchived,
  });

  final String id;
  final String name;
  final String type;
  final bool? isEssential;
  final bool isArchived;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        type: json['type'] as String,
        isEssential: json['is_essential'] as bool?,
        isArchived: json['is_archived'] as bool,
      );
}
