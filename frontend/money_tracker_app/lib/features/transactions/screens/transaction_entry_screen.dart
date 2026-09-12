import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/transaction.dart';
import '../providers/transaction_provider.dart';

// M1 ships without category CRUD (M2) — the seeded defaults from the
// backend migration are hardcoded here as a stopgap, matching the
// deterministic uuid.uuid5(NAMESPACE_DNS, "moneytracker.category.<name>")
// ids the migration now computes (0001_initial_schema.py), so these values
// are stable across any fresh migration run instead of the old random
// uuid.uuid4() ids. Replace with a real category fetch once
// GET /api/v1/categories exists in M2.
const _placeholderCategories = <String, String>{
  'Food': '998d9800-24a4-546b-bd8d-ba9da62a8c34',
  'Transport': 'a4bc6c20-407d-54ff-b000-88e50cc1af90',
  'Housing': 'f6bf3470-d8c9-59bf-9195-e686c79f041f',
  'Salary': '75da12ec-3bee-505e-aa31-20caa12f7e00',
};

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() => _TransactionEntryScreenState();
}

class _TransactionEntryScreenState extends ConsumerState<TransactionEntryScreen> {
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = 'expense';
  String _category = _placeholderCategories.keys.first;
  DateTime _occurredOn = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final entryState = ref.watch(transactionEntryControllerProvider);

    ref.listen(transactionEntryControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Transaction saved')),
        );
        _amountController.clear();
        _noteController.clear();
        setState(() {
          _type = 'expense';
          _category = _placeholderCategories.keys.first;
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
              items: _placeholderCategories.keys
                  .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                  .toList(),
              onChanged: (value) => setState(() => _category = value ?? _category),
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
    final draft = TransactionDraft(
      categoryId: _placeholderCategories[_category]!,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
