# Flutter performance

Measure in profile mode on a real (preferably low-end) device:

```bash
flutter run --profile
# DevTools: Performance (frame chart, jank), CPU profiler, Memory, "Track widget rebuilds"
```

Debug mode is not representative (JIT, assertions). Impeller is the default renderer on
iOS and on modern Android; shader compilation jank is mostly gone there.

## Build and rebuild

| Problem | Fix |
| --- | --- |
| `FutureBuilder(future: fetch())` / `StreamBuilder(stream: watch())` created in `build` | Create once in `initState`, a `late final` field, or a provider; pass the variable |
| Big `build` methods rebuilding everything on small changes | Split into smaller widgets (classes, not helper methods), `const` constructors, push state down |
| `MediaQuery.of(context)` in many widgets | `MediaQuery.sizeOf(context)`, `paddingOf`, `viewInsetsOf`: rebuild only on that aspect |
| `context.watch` / `ref.watch` of a large object | Select the field you need (`context.select`, `ref.watch(p.select(...))`, `BlocSelector`) |
| `setState` at the top of a large tree | Move state into the widget that changes, or use `ValueListenableBuilder` |
| `Opacity` / `ClipPath` / `saveLayer` in animations | `FadeTransition`, `AnimatedOpacity`, pre-clipped images; avoid `saveLayer` |

## Lists and scrolling

- `ListView.builder` / `.separated` / `SliverList` for long or dynamic lists, never
  `ListView(children: items.map(...).toList())`.
- Avoid `shrinkWrap: true` in scrollables of unknown length; use slivers
  (`CustomScrollView`) to combine sections.
- Give items a fixed `itemExtent` or `prototypeItem` when heights are uniform.
- Keys (`ValueKey(item.id)`) when items reorder.

## Images

- `cached_network_image` or `Image.network` with `cacheWidth`/`cacheHeight` to decode at
  display size (large photos decoded at full resolution cause memory spikes and OOM).
- `precacheImage` for hero images on the next screen.
- Prefer WebP; SVG via `flutter_svg` for icons.

## Heavy work

- JSON parsing of large payloads, image processing, crypto: `Isolate.run(() => ...)`
  (or `compute`) so the UI thread keeps 60/120 fps.
- Debounce search fields; paginate API calls.

## Startup

- Keep `main()` minimal: initialise only what the first screen needs; defer analytics,
  remote config and heavy plugins.
- Native splash (`flutter_native_splash`) instead of a Dart splash screen with delays.
- Measure with `flutter run --profile --trace-startup` (writes `start_up_info.json`).
