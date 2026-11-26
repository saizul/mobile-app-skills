# React Native performance

Profile a **release** build on a real low-end Android device; dev mode is much slower and
misleading.

- React DevTools Profiler: which components re-render and why
- Perf Monitor (dev menu): JS and UI frame rates
- Android Studio Profiler / Xcode Instruments: native CPU, memory, startup
- `react-native-performance` or Sentry/Firebase performance traces for startup and screens

## Lists

| Problem | Fix |
| --- | --- |
| `ScrollView` with `items.map(...)` for long lists | `FlatList`, or `@shopify/flash-list` for large/complex lists |
| Missing `keyExtractor` / unstable keys | `keyExtractor={item => item.id}` |
| Heavy `renderItem` re-rendering | `React.memo` row components, stable callbacks (`useCallback`), avoid inline objects in props |
| Variable heights measured on the fly | `getItemLayout` for fixed heights (FlatList), accurate item size hints (FlashList) |
| Images in rows | Sized thumbnails, `expo-image` caching, avoid decoding full-size photos |

## Re-renders

- Keep state close to where it is used; split contexts so a change does not re-render
  the whole tree; select slices from stores (Zustand selectors, Redux `useSelector` with
  narrow selectors).
- `useMemo`/`useCallback` where profiling shows cost; React Compiler (available with
  React 19 toolchains) can automate memoization; enable it per project after testing.

## Animations and gestures

- `useNativeDriver: true` for `transform` and `opacity` with the Animated API.
- Reanimated worklets and Gesture Handler for gesture-driven or layout animations; keep
  JS-thread work out of animation frames.
- Avoid `setState` on every scroll event; use `Animated.event` or Reanimated scroll
  handlers.

## Startup

- Hermes on; inline requires / lazy screens (`React.lazy` with navigation, or
  `getComponent` in React Navigation) for heavy screens.
- Defer non-critical SDK initialisation until after first render.
- Keep the initial bundle small: remove `moment`, full `lodash`, unused polyfills.

## Release hygiene

- Strip `console.*` in production (`babel-plugin-transform-remove-console` under
  `env.production`).
- R8 on for Android release (`enableProguardInReleaseBuilds = true`) with library keep rules.
- Secure storage for tokens; never ship private API keys in JS (the bundle is readable).
