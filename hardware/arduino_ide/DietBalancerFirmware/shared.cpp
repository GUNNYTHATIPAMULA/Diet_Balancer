#include "shared.h"

Shared shared;
portMUX_TYPE sharedMux = portMUX_INITIALIZER_UNLOCKED;

void setLastError(const char* msg) {
  SHARED_LOCK();
  strlcpy(shared.lastError, msg, sizeof(shared.lastError));
  SHARED_UNLOCK();
}
