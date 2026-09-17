import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/monthly_summary.dart';
import '../providers/dashboard_provider.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summaryAsync = ref.watch(monthlySummaryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: summaryAsync.when(
        data: (summary) => ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text('Income: ${summary.totalIncome}', key: const Key('total_income')),
            Text('Expense: ${summary.totalExpense}', key: const Key('total_expense')),
            Text('Net: ${summary.net}', key: const Key('total_net')),
            const SizedBox(height: 24),
            const Text('By category', style: TextStyle(fontWeight: FontWeight.bold)),
            ...summary.byCategory.map((item) => _BreakdownRow(item: item, summary: summary)),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load summary: $error')),
      ),
    );
  }
}

class _BreakdownRow extends StatelessWidget {
  const _BreakdownRow({required this.item, required this.summary});

  final CategoryBreakdown item;
  final MonthlySummary summary;

  @override
  Widget build(BuildContext context) {
    final maxAmount = summary.byCategory
        .map((e) => double.tryParse(e.amount) ?? 0)
        .fold<double>(0, (max, value) => value > max ? value : max);
    final amount = double.tryParse(item.amount) ?? 0;
    final fraction = maxAmount == 0 ? 0.0 : (amount / maxAmount).clamp(0.0, 1.0);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${item.categoryName} — ${item.amount}'),
          FractionallySizedBox(
            widthFactor: fraction,
            alignment: Alignment.centerLeft,
            child: Container(height: 8, color: Theme.of(context).colorScheme.primary),
          ),
        ],
      ),
    );
  }
}
