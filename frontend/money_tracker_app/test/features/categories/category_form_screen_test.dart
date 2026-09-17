import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/screens/category_form_screen.dart';

void main() {
  // CategoryFormScreen watches categoryControllerProvider directly during
  // build (for its loading/error state), which depends on apiClientProvider
  // -> supabaseClientProvider -> Supabase.instance.client, same as M1's
  // TransactionEntryScreen. This test never submits, so no real network
  // call happens, but Supabase.initialize() still needs to have run once
  // (see test/widget_test.dart for why the shared_preferences channel is
  // mocked here too).
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

  testWidgets('CategoryFormScreen essential toggle only shows for expense type', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: CategoryFormScreen())),
    );

    expect(find.byKey(const Key('category_essential_toggle')), findsOneWidget);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);
  });
}
