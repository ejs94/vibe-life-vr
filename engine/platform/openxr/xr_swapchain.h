#ifndef XR_SWAPCHAIN_H
#define XR_SWAPCHAIN_H

#include "xr_core.h"

#ifdef XASH_OPENXR

#include <openxr/openxr.h>

typedef struct {
    XrSwapchain swapchain;
    uint32_t width;
    uint32_t height;
    uint32_t imageCount;
    uint32_t *images;
    uint32_t *fbos;
    uint32_t currentImageIndex;
} xr_eye_swapchain_t;

extern EXPORT xr_eye_swapchain_t g_xrEyeSwapchains[2];
extern EXPORT XrView g_xrViews[2];
extern EXPORT qboolean g_xrSwapchainsReady;

EXPORT qboolean XR_CreateSwapchains( void );
EXPORT void XR_DestroySwapchains( void );

EXPORT qboolean XR_WaitFrame( XrFrameState *outFrameState );
EXPORT qboolean XR_BeginFrame( void );
EXPORT void XR_BeginEye( int eye );
EXPORT void XR_EndEye( int eye );
EXPORT void XR_EndFrame( void );

EXPORT qboolean XR_IsQuadHudActive( void );
EXPORT void XR_SetQuadHud( qboolean enabled );
EXPORT XrTime XR_GetPredictedDisplayTime( void );

#else // !XASH_OPENXR

static inline qboolean XR_IsQuadHudActive( void ) { return false; }
static inline void XR_SetQuadHud( qboolean enabled ) {}
static inline int64_t XR_GetPredictedDisplayTime( void ) { return 0; }

#endif // XASH_OPENXR

#endif // XR_SWAPCHAIN_H
