import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/dashboard/models/monthly_summary.dart';
import 'package:money_tracker_app/features/dashboard/providers/dashboard_provider.dart';
import 'package:money_tracker_app/features/dashboard/screens/dashboard_screen.dart';

void main() {
  testWidgets('DashboardScreen renders totals and category breakdown', (tester) async {
    final summary = MonthlySummary(
      month: '2026-09',
      totalIncome: '1000.00',
      totalExpense: '400.00',
      net: '600.00',
      byCategory: [
        CategoryBreakdown(categoryId: '1', categoryName: 'Food', type: 'expense', amount: '400.00'),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [monthlySummaryProvider.overrideWith((ref) async => summary)],
        child: const MaterialApp(home: DashboardScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Income: 1000.00'), findsOneWidget);
    expect(find.text('Expense: 400.00'), findsOneWidget);
    expect(find.text('Net: 600.00'), findsOneWidget);
    expect(find.text('Food — 400.00'), findsOneWidget);
  });
}
