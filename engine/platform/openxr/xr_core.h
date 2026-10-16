#ifndef XR_CORE_H
#define XR_CORE_H

#include "xash3d_types.h"

struct convar_s;
typedef struct convar_s convar_t;
#ifdef XASH_OPENXR

#include <openxr/openxr.h>

extern XrInstance g_xrInstance;
extern XrSystemId g_xrSystemId;
extern XrSession g_xrSession;
extern XrSpace g_xrLocalSpace;
extern XrSpace g_xrViewSpace;
extern XrSessionState g_xrSessionState;
extern qboolean g_xrSessionRunning;

extern EXPORT convar_t *vr_smoothturn;
extern EXPORT convar_t *vr_snap_angle;
extern EXPORT convar_t *vr_walkdirection;
extern EXPORT convar_t *vr_lasersight;
extern EXPORT convar_t *vr_headtorch;
extern EXPORT convar_t *vr_lefthanded;
extern EXPORT convar_t *vr_weapon_pitchadjust;
extern EXPORT convar_t *vr_weapon_yawadjust;
extern EXPORT convar_t *vr_weapon_rolladjust;
extern EXPORT convar_t *vr_weapon_offset_forward;
extern EXPORT convar_t *vr_weapon_offset_right;
extern EXPORT convar_t *vr_weapon_offset_up;
extern EXPORT convar_t *vr_height_adjust;
extern EXPORT convar_t *vr_hide_arms;

extern EXPORT convar_t *vr_worldscale;
extern EXPORT convar_t *vr_haptics_enabled;
extern EXPORT convar_t *vr_haptics_intensity;
extern EXPORT convar_t *vr_pointer_hud;
extern EXPORT convar_t *vr_test_hands;
extern EXPORT convar_t *vr_test_hand_pitch;
extern EXPORT convar_t *vr_test_hand_yaw;
extern EXPORT convar_t *vr_test_click;

EXPORT void XR_RegisterCVars( void );
EXPORT qboolean XR_Init( void );
EXPORT qboolean XR_InitGraphics( void );
EXPORT void XR_EnsureCurrent( void );
EXPORT void* XR_GetGraphicsBinding( void );
EXPORT qboolean XR_CreateSession( void );
EXPORT qboolean XR_IsActive( void );
EXPORT void XR_Shutdown( void );
EXPORT void XR_PollEvents( void );
EXPORT void XR_SyncInputs( void );
EXPORT qboolean XR_BeginFrame( void );
EXPORT void XR_EndFrame( void );
EXPORT void XR_EndMenuFrame( void );
EXPORT void XR_RunMenuFrame( void );

EXPORT void XR_GetHeadOrientation( vec3_t out_angles );
EXPORT void XR_GetEyePosition( int eye, vec3_t out_origin );
EXPORT void XR_GetEyeFrustum( int eye, float nearZ, float farZ, float *left, float *right, float *bottom, float *top );
EXPORT void XR_QuatToEuler( const XrQuaternionf *q, vec3_t out_angles );

#else // !XASH_OPENXR

static inline void XR_RegisterCVars( void ) {}
static inline qboolean XR_Init( void ) { return false; }
static inline qboolean XR_InitGraphics( void ) { return false; }
static inline void XR_EnsureCurrent( void ) {}
static inline void* XR_GetGraphicsBinding( void ) { return NULL; }
static inline qboolean XR_CreateSession( void ) { return false; }
static inline qboolean XR_IsActive( void ) { return false; }
static inline void XR_Shutdown( void ) {}
static inline void XR_PollEvents( void ) {}
static inline void XR_SyncInputs( void ) {}
static inline qboolean XR_BeginFrame( void ) { return false; }
static inline void XR_EndFrame( void ) {}
static inline void XR_EndMenuFrame( void ) {}
static inline void XR_RunMenuFrame( void ) {}
static inline void XR_GetHeadOrientation( vec3_t out_angles ) { if( out_angles ) VectorClear( out_angles ); }
static inline void XR_GetEyePosition( int eye, vec3_t out_origin ) { if( out_origin ) VectorClear( out_origin ); }
static inline void XR_GetEyeFrustum( int eye, float nearZ, float farZ, float *left, float *right, float *bottom, float *top ) { if( left ) *left = 0; if( right ) *right = 0; if( bottom ) *bottom = 0; if( top ) *top = 0; }

#endif // XASH_OPENXR

#endif // XR_CORE_H
