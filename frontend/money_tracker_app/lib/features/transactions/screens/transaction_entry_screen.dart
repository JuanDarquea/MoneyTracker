import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/transaction.dart';
import '../providers/transaction_provider.dart';

// M1 ships without category CRUD (M2) — the seeded defaults from the
// backend migration are hardcoded here as a stopgap, matching the ids
// Backend's Task 2 seed inserts in a fixed order won't be stable, so
// this is placeholder UI wiring only: replace with a real category
// fetch once GET /api/v1/categories exists in M2.
const _placeholderCategories = <String>['Food', 'Transport', 'Housing', 'Salary'];

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() => _TransactionEntryScreenState();
}

class _TransactionEntryScreenState extends ConsumerState<TransactionEntryScreen> {
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = 'expense';
  String _category = _placeholderCategories.first;
  DateTime _occurredOn = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final entryState = ref.watch(transactionEntryControllerProvider);

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
              onSelectionChanged: (selection) => setState(() => _type = selection.first),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('amount_field'),
              controller: _amountController,
              decoration: const InputDecoration(labelText: 'Amount'),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            DropdownButton<String>(
              key: const Key('category_dropdown'),
              value: _category,
              items: _placeholderCategories
                  .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                  .toList(),
              onChanged: (value) => setState(() => _category = value ?? _category),
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

  void _submit() {
    final draft = TransactionDraft(
      categoryId: _category,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
