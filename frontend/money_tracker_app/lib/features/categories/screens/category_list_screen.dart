import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/category.dart';
import '../providers/category_provider.dart';
import 'category_form_screen.dart';

class CategoryListScreen extends ConsumerWidget {
  const CategoryListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categoriesAsync = ref.watch(categoryListProvider);

    ref.listen(categoryControllerProvider, (previous, next) {
      if (next.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update category: ${next.error}')),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Categories')),
      body: categoriesAsync.when(
        data: (categories) => ListView(
          children: categories.map((category) => _CategoryTile(category: category)).toList(),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load categories: $error')),
      ),
      floatingActionButton: FloatingActionButton(
        key: const Key('add_category_button'),
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const CategoryFormScreen()),
        ),
        child: const Icon(Icons.add),
      ),
    );
  }
}

class _CategoryTile extends ConsumerWidget {
  const _CategoryTile({required this.category});

  final Category category;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListTile(
      title: Text(category.name),
      subtitle: Text(category.type),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (category.type == 'expense')
            Switch(
              key: Key('essential_toggle_${category.id}'),
              value: category.isEssential ?? false,
              onChanged: (value) =>
                  ref.read(categoryControllerProvider.notifier).setEssential(category.id, value),
            ),
          IconButton(
            key: Key('archive_button_${category.id}'),
            icon: const Icon(Icons.archive_outlined),
            onPressed: () => ref.read(categoryControllerProvider.notifier).archive(category.id),
          ),
        ],
      ),
    );
  }
}
