import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/auth/screens/login_screen.dart';
import 'package:money_tracker_app/features/auth/screens/signup_screen.dart';

void main() {
  // LoginScreen/SignupScreen watch authControllerProvider, which reads
  // Supabase.instance.client. Supabase.initialize() normally runs in main()
  // before the app starts; widget tests never run main(), so we replicate
  // the minimal setup here. Supabase.initialize() itself touches
  // shared_preferences (for local session storage) via a platform channel
  // that isn't wired up in the test environment, so that channel is mocked
  // to return an empty map — no real prefs storage or network access is
  // needed since these tests never trigger a sign-in/sign-up call.
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
      publishableKey: 'test-anon-key',
    );
  });

  testWidgets('LoginScreen shows email, password, and login button',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: LoginScreen())),
    );

    expect(find.byKey(const Key('email_field')), findsOneWidget);
    expect(find.byKey(const Key('password_field')), findsOneWidget);
    expect(find.byKey(const Key('login_button')), findsOneWidget);
  });

  testWidgets('Tapping "go to signup" navigates to SignupScreen',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: LoginScreen())),
    );

    await tester.tap(find.byKey(const Key('go_to_signup_link')));
    await tester.pumpAndSettle();

    expect(find.byType(SignupScreen), findsOneWidget);
  });
}
