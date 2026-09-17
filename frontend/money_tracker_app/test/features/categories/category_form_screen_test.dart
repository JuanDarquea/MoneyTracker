import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/screens/category_form_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  testWidgets('CategoryFormScreen has no essential toggle -- that tag now lives on transactions',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: CategoryFormScreen())),
    );

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);
  });
}
