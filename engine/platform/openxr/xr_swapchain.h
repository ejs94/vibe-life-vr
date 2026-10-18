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
EXPORT void XR_EndMenuFrame( void );

EXPORT qboolean XR_IsQuadHudActive( void );
EXPORT void XR_SetQuadHud( qboolean enabled );
EXPORT XrTime XR_GetPredictedDisplayTime( void );

EXPORT void XR_AnchorMenuQuad( void );
EXPORT void XR_ResetMenuAnchor( void );
EXPORT qboolean XR_IsMenuQuadAnchored( void );
EXPORT XrSpace XR_GetMenuQuadSpace( void );

EXPORT float XR_GetRoomscaleHeadDrop( void );

#else // !XASH_OPENXR

static inline void XR_EndMenuFrame( void ) {}
static inline qboolean XR_IsQuadHudActive( void ) { return false; }
static inline void XR_SetQuadHud( qboolean enabled ) {}
static inline int64_t XR_GetPredictedDisplayTime( void ) { return 0; }
static inline void XR_AnchorMenuQuad( void ) {}
static inline void XR_ResetMenuAnchor( void ) {}
static inline qboolean XR_IsMenuQuadAnchored( void ) { return false; }
static inline void* XR_GetMenuQuadSpace( void ) { return NULL; }
static inline float XR_GetRoomscaleHeadDrop( void ) { return 0.0f; }

#endif // XASH_OPENXR

#endif // XR_SWAPCHAIN_H
