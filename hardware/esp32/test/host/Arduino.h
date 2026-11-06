// Minimal Arduino stand-in so dispenser.cpp can run on a PC for logic tests.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
using std::max;
using std::min;
extern unsigned long fakeMillis;
inline unsigned long millis() { return fakeMillis; }
template <class T, class L, class H> T constrain(T v, L lo, H hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline size_t strlcpy(char* d, const char* s, size_t n) { size_t l = strlen(s); if (n) { size_t c = l >= n ? n - 1 : l; memcpy(d, s, c); d[c] = 0; } return l; }
class String {
 public:
  String(const char* s = "") : v(s) {}
  String(float f, int d) { char b[32]; snprintf(b, sizeof b, "%.*f", d, f); v = b; }
  const char* c_str() const { return v.c_str(); }
  bool operator==(const char* o) const { return v == o; }
  std::string v;
};
struct FakeSerial { template <class... A> void printf(const char* f, A... a) { if (getenv("VERBOSE")) ::printf(f, a...); } void println(const char*) {} };
extern FakeSerial Serial;
typedef int portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) (void)(x)
#define portEXIT_CRITICAL(x) (void)(x)
