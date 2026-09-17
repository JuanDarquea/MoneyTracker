import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/category_provider.dart';

class CategoryFormScreen extends ConsumerStatefulWidget {
  const CategoryFormScreen({super.key});

  @override
  ConsumerState<CategoryFormScreen> createState() => _CategoryFormScreenState();
}

class _CategoryFormScreenState extends ConsumerState<CategoryFormScreen> {
  final _nameController = TextEditingController();
  String _type = 'expense';
  bool _isEssential = false;

  @override
  Widget build(BuildContext context) {
    final controllerState = ref.watch(categoryControllerProvider);

    ref.listen(categoryControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        Navigator.of(context).pop();
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('New category')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            TextField(
              key: const Key('category_name_field'),
              controller: _nameController,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              key: const Key('category_type_toggle'),
              segments: const [
                ButtonSegment(value: 'expense', label: Text('Expense')),
                ButtonSegment(value: 'income', label: Text('Income')),
              ],
              selected: {_type},
              onSelectionChanged: (selection) => setState(() {
                _type = selection.first;
                if (_type == 'income') _isEssential = false;
              }),
            ),
            if (_type == 'expense')
              SwitchListTile(
                key: const Key('category_essential_toggle'),
                title: const Text('Essential'),
                value: _isEssential,
                onChanged: (value) => setState(() => _isEssential = value),
              ),
            const SizedBox(height: 24),
            if (controllerState.hasError)
              Text('Failed to save: ${controllerState.error}', style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              key: const Key('save_category_button'),
              onPressed: controllerState.isLoading ? null : _submit,
              child: controllerState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  void _submit() {
    ref.read(categoryControllerProvider.notifier).create(
          name: _nameController.text.trim(),
          type: _type,
          isEssential: _type == 'expense' ? _isEssential : null,
        );
  }
}
