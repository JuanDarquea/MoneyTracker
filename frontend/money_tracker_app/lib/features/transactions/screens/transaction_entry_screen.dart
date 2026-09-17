import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../categories/providers/category_provider.dart';
import '../models/transaction.dart';
import '../providers/transaction_provider.dart';

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() => _TransactionEntryScreenState();
}

class _TransactionEntryScreenState extends ConsumerState<TransactionEntryScreen> {
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = 'expense';
  String? _categoryId;
  DateTime _occurredOn = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final entryState = ref.watch(transactionEntryControllerProvider);
    final categoriesAsync = ref.watch(categoryListProvider);

    ref.listen(transactionEntryControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Transaction saved')),
        );
        _amountController.clear();
        _noteController.clear();
        setState(() {
          _type = 'expense';
          _categoryId = null;
          _occurredOn = DateTime.now();
        });
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Add transaction')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            SegmentedButton<String>(
              key: const Key('type_toggle'),
              segments: const [
                ButtonSegment(value: 'expense', label: Text('Expense')),
                ButtonSegment(value: 'income', label: Text('Income')),
              ],
              selected: {_type},
              onSelectionChanged: (selection) => setState(() {
                _type = selection.first;
                _categoryId = null;
              }),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('amount_field'),
              controller: _amountController,
              decoration: const InputDecoration(labelText: 'Amount'),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            categoriesAsync.when(
              data: (categories) {
                final filtered = categories.where((c) => c.type == _type).toList();
                if (_categoryId == null && filtered.isNotEmpty) {
                  _categoryId = filtered.first.id;
                }
                return DropdownButton<String>(
                  key: const Key('category_dropdown'),
                  value: _categoryId,
                  items: filtered
                      .map((c) => DropdownMenuItem(value: c.id, child: Text(c.name)))
                      .toList(),
                  onChanged: (value) => setState(() => _categoryId = value),
                );
              },
              loading: () => const CircularProgressIndicator(key: Key('category_dropdown')),
              error: (error, _) =>
                  Text('Failed to load categories: $error', key: const Key('category_dropdown')),
            ),
            const SizedBox(height: 12),
            InkWell(
              key: const Key('date_field'),
              onTap: _pickDate,
              child: InputDecorator(
                decoration: const InputDecoration(labelText: 'Date'),
                child: Text(
                  '${_occurredOn.year.toString().padLeft(4, '0')}-'
                  '${_occurredOn.month.toString().padLeft(2, '0')}-'
                  '${_occurredOn.day.toString().padLeft(2, '0')}',
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('note_field'),
              controller: _noteController,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
            const SizedBox(height: 24),
            if (entryState.hasError)
              Text('Failed to save: ${entryState.error}', style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              key: const Key('submit_button'),
              onPressed: entryState.isLoading ? null : _submit,
              child: entryState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Save transaction'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _occurredOn,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _occurredOn = picked);
    }
  }

  void _submit() {
    final categoryId = _categoryId;
    if (categoryId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No category available for this type')),
      );
      return;
    }
    final draft = TransactionDraft(
      categoryId: categoryId,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
