import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/transactions/screens/transaction_entry_screen.dart';

void main() {
  // TransactionEntryScreen watches transactionEntryControllerProvider, which
  // depends on apiClientProvider -> supabaseClientProvider, which reads
  // Supabase.instance.client. Supabase.initialize() normally runs in main()
  // before the app starts; widget tests never run main(), so we replicate
  // the minimal setup here, same as test/widget_test.dart does for the auth
  // screens. Supabase.initialize() itself touches shared_preferences (for
  // local session storage) via a platform channel that isn't wired up in
  // the test environment, so that channel is mocked to return an empty map
  // — no real prefs storage or network access is needed since this test
  // never triggers a submit.
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel(
    'plugins.flutter.io/shared_preferences',
  );
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(
      url: 'http://localhost:54321',
      anonKey: 'test-anon-key',
    );
  });

  testWidgets('TransactionEntryScreen exposes exactly the required fields',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: TransactionEntryScreen())),
    );

    expect(find.byKey(const Key('amount_field')), findsOneWidget);
    expect(find.byKey(const Key('type_toggle')), findsOneWidget);
    expect(find.byKey(const Key('category_dropdown')), findsOneWidget);
    expect(find.byKey(const Key('note_field')), findsOneWidget);
    expect(find.byKey(const Key('submit_button')), findsOneWidget);
  });
}
