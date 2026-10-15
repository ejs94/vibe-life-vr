#ifndef XR_INPUT_H
#define XR_INPUT_H

#include "xr_core.h"
struct usercmd_s;
typedef struct usercmd_s usercmd_t;

typedef enum {
	VR_HAND_LEFT = 0,
	VR_HAND_RIGHT = 1,
	VR_HAND_BOTH = 2
} vr_hand_t;

typedef enum {
	VR_HAPTIC_WEAPON_GLOCK = 0,
	VR_HAPTIC_WEAPON_PYTHON,
	VR_HAPTIC_WEAPON_SHOTGUN,
	VR_HAPTIC_WEAPON_SHOTGUN_DOUBLE,
	VR_HAPTIC_WEAPON_MP5,
	VR_HAPTIC_WEAPON_MP5_GRENADE,
	VR_HAPTIC_WEAPON_CROSSBOW,
	VR_HAPTIC_WEAPON_RPG,
	VR_HAPTIC_WEAPON_GAUSS,
	VR_HAPTIC_WEAPON_GAUSS_CHARGED,
	VR_HAPTIC_WEAPON_EGON,
	VR_HAPTIC_WEAPON_CROWBAR,
	VR_HAPTIC_WEAPON_GENERIC,
	VR_HAPTIC_DAMAGE_LIGHT,
	VR_HAPTIC_DAMAGE_MEDIUM,
	VR_HAPTIC_DAMAGE_HEAVY,
	VR_HAPTIC_SUIT_CHARGE,
	VR_HAPTIC_GEIGER,
	VR_HAPTIC_UI_CLICK
} vr_haptic_effect_t;

#ifdef XASH_OPENXR

typedef struct {
    qboolean attack;
    qboolean attack2;
    qboolean jump;
    qboolean duck;
    qboolean use;
    qboolean reload;
    qboolean flashlight;
    qboolean menu;
    qboolean sprint;
    float gripLeft;
    float gripRight;
    float moveX;
    float moveY;
    float turnX;
    float turnY;

    XrPosef leftHandPose;
    XrPosef rightHandPose;
    XrVector3f leftHandVelocity;
    XrVector3f rightHandVelocity;
    qboolean leftHandActive;
    qboolean rightHandActive;
} xr_input_state_t;

extern EXPORT xr_input_state_t g_xrInputState;

EXPORT qboolean XR_InitInput( void );
EXPORT void XR_ShutdownInput( void );
EXPORT void XR_InputAppendMove( usercmd_t *cmd, float frametime );
EXPORT float XR_GetPlayerTurnYaw( void );

EXPORT qboolean XR_GetPrimaryHandTransform( vec3_t out_origin, vec3_t out_angles );
EXPORT qboolean XR_GetPrimaryHandVelocity( vec3_t out_velocity );
EXPORT qboolean XR_GetPrimaryHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles );
EXPORT qboolean XR_GetRightHandTransform( vec3_t out_origin, vec3_t out_angles );
EXPORT qboolean XR_GetLeftHandTransform( vec3_t out_origin, vec3_t out_angles );
EXPORT qboolean XR_GetRightHandVelocity( vec3_t out_velocity );
EXPORT qboolean XR_GetLeftHandVelocity( vec3_t out_velocity );
EXPORT qboolean XR_GetRightHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles );

EXPORT void XR_ApplyHapticFeedback( int hand, float duration_seconds, float frequency_hz, float amplitude );
EXPORT void XR_StopHapticFeedback( int hand );
EXPORT void XR_TriggerHapticEffect( int hand, vr_haptic_effect_t effect, float intensity_scale );
EXPORT void XR_DispatchWeaponHaptic( const char *event_name );

EXPORT qboolean XR_GetPointerLaserRay( vec3_t out_start, vec3_t out_end, qboolean *out_hit, float *out_u, float *out_v );
EXPORT void XR_UpdatePointerCursor( void );
qboolean XR_GetPointerCursorPos( int *out_x, int *out_y, qboolean *out_hit );

#else // !XASH_OPENXR

static inline qboolean XR_InitInput( void ) { return false; }
static inline void XR_ShutdownInput( void ) {}
static inline void XR_InputAppendMove( usercmd_t *cmd, float frametime ) {}
static inline float XR_GetPlayerTurnYaw( void ) { return 0.0f; }

static inline qboolean XR_GetPrimaryHandTransform( vec3_t out_origin, vec3_t out_angles ) { return false; }
static inline qboolean XR_GetPrimaryHandVelocity( vec3_t out_velocity ) { return false; }
static inline qboolean XR_GetPrimaryHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles ) { return false; }
static inline qboolean XR_GetRightHandTransform( vec3_t out_origin, vec3_t out_angles ) { return false; }
static inline qboolean XR_GetLeftHandTransform( vec3_t out_origin, vec3_t out_angles ) { return false; }
static inline qboolean XR_GetRightHandVelocity( vec3_t out_velocity ) { return false; }
static inline qboolean XR_GetLeftHandVelocity( vec3_t out_velocity ) { return false; }
static inline qboolean XR_GetRightHandMuzzleTransform( vec3_t out_muzzle_offset, vec3_t out_aim_angles ) { return false; }

static inline void XR_ApplyHapticFeedback( int hand, float duration_seconds, float frequency_hz, float amplitude ) {}
static inline void XR_StopHapticFeedback( int hand ) {}
static inline void XR_TriggerHapticEffect( int hand, vr_haptic_effect_t effect, float intensity_scale ) {}
static inline void XR_DispatchWeaponHaptic( const char *event_name ) {}

static inline qboolean XR_GetPointerLaserRay( vec3_t out_start, vec3_t out_end, qboolean *out_hit, float *out_u, float *out_v ) { return false; }
static inline void XR_UpdatePointerCursor( void ) {}
static inline qboolean XR_GetPointerCursorPos( int *out_x, int *out_y, qboolean *out_hit ) { return false; }

#endif // XASH_OPENXR

#endif // XR_INPUT_H
