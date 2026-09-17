import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/categories/screens/category_list_screen.dart';

void main() {
  testWidgets(
      'CategoryListScreen renders fetched categories with an essential toggle only for expense categories',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isEssential: true, isArchived: false),
      Category(id: '2', name: 'Salary', type: 'income', isEssential: null, isArchived: false),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => categories)],
        child: const MaterialApp(home: CategoryListScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Food'), findsOneWidget);
    expect(find.text('Salary'), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle_1')), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle_2')), findsNothing);
    expect(find.byKey(const Key('add_category_button')), findsOneWidget);
  });
}
