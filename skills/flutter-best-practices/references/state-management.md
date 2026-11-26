# Choosing state management

Separate the kinds of state first:

- **Ephemeral UI state** (a text field, an expanded tile, an animation): `StatefulWidget`
  with `setState`, or `ValueNotifier` + `ValueListenableBuilder`. No library needed.
- **App state** (session, cart, settings, server data shared across screens): pick one
  approach below.
- **Server cache** (lists fetched from an API): treat as app state with loading/error
  states, caching and refresh; Riverpod's `AsyncValue` and Bloc states both model this.

| Approach | Good fit | Watch out |
| --- | --- | --- |
| `setState` / `ValueNotifier` / `ChangeNotifier` + `InheritedWidget` | Small apps, prototypes, packages | Prop drilling, manual disposal |
| Provider | Simple apps already using it; the Flutter docs' classic example | Mostly superseded by Riverpod for new code; `context.watch` in the wrong place rebuilds a lot |
| Riverpod (with `riverpod_generator`) | Most new apps: compile-safe DI, async state, testability without `BuildContext` | Learn the provider kinds; keep code generation in CI |
| Bloc / Cubit | Larger teams wanting explicit events/states, strict layering, strong tooling (`bloc_test`) | More boilerplate; use Cubit for simple cases |
| Signals | Fine-grained reactivity, small to mid apps | Younger ecosystem |
| GetX | Existing code only | Mixes routing, DI and state with global singletons; hard to test; not recommended for new projects |

Rules of thumb:

1. One approach for app state per codebase. Mixing Provider + Bloc + GetX is the most
   common source of confusing data flow (`state.mixed` finding).
2. Keep business logic out of widgets: repositories (data), notifiers/blocs (logic),
   widgets (UI). Test logic without Flutter.
3. Immutable state classes (`freezed` or hand-written `copyWith` + `==`).
4. Dispose what you create (controllers, streams, subscriptions); libraries do this for
   you when you use their lifecycle (`autoDispose`, `BlocProvider`).
5. Migrating: wrap new features in the chosen approach and move old screens when you touch
   them; no big-bang rewrites.

## Suggested structure (feature-first)

```
lib/
  app/                 app widget, router, theme, DI setup
  core/                shared utilities, error types, network client
  features/
    budgets/
      data/            DTOs, API clients, repositories
      domain/          models, use cases (optional for small apps)
      presentation/    screens, widgets, notifiers/blocs
  l10n/                ARB files
test/                  mirrors lib/
```
