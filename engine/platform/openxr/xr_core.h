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
extern XrSpace g_xrMenuQuadSpace;
extern XrSessionState g_xrSessionState;
extern qboolean g_xrSessionRunning;

extern EXPORT convar_t *vr_smoothturn;
extern EXPORT convar_t *vr_snap_angle;
extern EXPORT convar_t *vr_walkdirection;
extern EXPORT convar_t *vr_lasersight;
extern EXPORT convar_t *vr_headtorch;
extern EXPORT convar_t *vr_lefthanded;
extern EXPORT convar_t *vr_lefthanded_mirror_grip;
extern EXPORT convar_t *vr_weapon_pitchadjust;
extern EXPORT convar_t *vr_weapon_yawadjust;
extern EXPORT convar_t *vr_weapon_rolladjust;
extern EXPORT convar_t *vr_weapon_offset_forward;
extern EXPORT convar_t *vr_weapon_offset_right;
extern EXPORT convar_t *vr_weapon_offset_up;
extern EXPORT convar_t *vr_hand_offset_forward;
extern EXPORT convar_t *vr_hand_offset_right;
extern EXPORT convar_t *vr_hand_offset_up;
extern EXPORT convar_t *vr_height_adjust;
extern EXPORT convar_t *vr_hide_arms;

extern EXPORT convar_t *vr_twohanded;
extern EXPORT convar_t *vr_menu_distance;
extern EXPORT convar_t *vr_menu_scale;

extern EXPORT convar_t *vr_worldscale;
extern EXPORT convar_t *vr_haptics_enabled;
extern EXPORT convar_t *vr_haptics_intensity;
extern EXPORT convar_t *vr_pointer_hud;
extern EXPORT convar_t *vr_test_hands;
extern EXPORT convar_t *vr_test_hand_pitch;
extern EXPORT convar_t *vr_test_hand_yaw;
extern EXPORT convar_t *vr_test_click;
extern EXPORT convar_t *vr_test_head;
extern EXPORT convar_t *vr_test_head_pitch;
extern EXPORT convar_t *vr_test_head_yaw;
extern EXPORT convar_t *vr_test_head_roll;
extern EXPORT convar_t *vr_test_head_drop;
extern EXPORT convar_t *vr_test_headgesture;
extern EXPORT convar_t *vr_audio_hrtf;
extern EXPORT convar_t *vr_finger_curling;
extern EXPORT convar_t *vr_finger_curl_scale;
extern EXPORT convar_t *vr_offhand_render;
extern EXPORT convar_t *vr_hands_always_visible;
extern EXPORT convar_t *vr_primary_hand_model;
extern EXPORT convar_t *vr_hand_death_visible;
extern EXPORT convar_t *vr_test_finger_curl;
extern EXPORT convar_t *vr_proximity_scope;
extern EXPORT convar_t *vr_gesture_use;
extern EXPORT convar_t *vr_melee_swing;
extern EXPORT convar_t *vr_offhand_grab;
extern EXPORT convar_t *vr_debug_grab;
extern EXPORT convar_t *vr_scope_mode;
extern EXPORT convar_t *vr_scope_zoom;
extern EXPORT convar_t *vr_scope_radius;
extern EXPORT convar_t *vr_scope_reticle;
extern EXPORT convar_t *vr_debug_ladder;
extern EXPORT convar_t *vr_debug_impacts;
extern EXPORT convar_t *vr_debug_hand;
extern EXPORT convar_t *vr_debug_hand_pose;
extern EXPORT convar_t *vr_grip_probe;
extern EXPORT convar_t *vr_foregrip;
extern EXPORT convar_t *vr_calibration_stick;
extern EXPORT convar_t *vr_weapon_idle_mode;
extern EXPORT convar_t *vr_weapon_anchor_root;
extern EXPORT convar_t *vr_weapon_skip_draw;
extern EXPORT convar_t *vr_weapon_no_deploy;
extern EXPORT convar_t *vr_melee_suppress_attack_anim;
extern EXPORT convar_t *vr_weapon_true_depth;
extern EXPORT convar_t *vr_weapon_pullback;
extern EXPORT convar_t *vr_debug_reload;
extern EXPORT convar_t *vr_test_btn_reload;
extern EXPORT convar_t *vr_test_btn_altfire;
extern EXPORT convar_t *vr_test_btn_jump;
extern EXPORT convar_t *vr_test_btn_reload_left;
extern EXPORT convar_t *vr_test_btn_jump_left;
extern EXPORT convar_t *vr_test_btn_menu;
extern EXPORT convar_t *vr_test_stick_x;
extern EXPORT convar_t *vr_test_stick_y;
extern EXPORT convar_t *vr_test_move_probe;
extern EXPORT convar_t *vr_test_hand_angle_probe;
extern EXPORT convar_t *vr_test_offhand_grip;
extern EXPORT convar_t *vr_physical_crouch;
extern EXPORT convar_t *vr_menu_tab;

// 3D visual bullet impact debug marker tracking structure
typedef struct vr_debug_impact_s
{
    vec3_t start;       // Weapon muzzle position
    vec3_t end;         // Exact surface impact position
    vec3_t normal;      // Impact surface normal
    double expire_time; // Absolute expiration timestamp in host.realtime
    int shot_id;        // Monotonically increasing shot identifier
} vr_debug_impact_t;

#define MAX_VR_DEBUG_IMPACTS 32
extern EXPORT vr_debug_impact_t g_vrDebugImpacts[MAX_VR_DEBUG_IMPACTS];
extern EXPORT int g_vrNumDebugImpacts;
extern EXPORT int g_vrTotalShotsFired;

EXPORT void XR_AddDebugBulletImpact( const float *start, const float *end, const float *normal );
EXPORT void XR_ClearDebugBulletImpacts( void );

EXPORT void XR_RegisterCVars( void );
EXPORT qboolean XR_Init( void );
EXPORT qboolean XR_InitGraphics( void );
EXPORT void XR_EnsureCurrent( void );
EXPORT void* XR_GetGraphicsBinding( void );
EXPORT qboolean XR_CreateSession( void );
EXPORT qboolean XR_IsActive( void );
EXPORT qboolean XR_IsSessionRunning( void );
EXPORT qboolean XR_IsInitialized( void );
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
EXPORT void XR_ResetHeadOriginCalibration( void );
EXPORT qboolean XR_GetHeadCenterTransform( vec3_t out_origin_offset, vec3_t out_angles );
EXPORT qboolean XR_GetHeadCenterTransformWithBasis( vec3_t out_origin_offset, vec3_t out_forward, vec3_t out_right, vec3_t out_up );

#else // !XASH_OPENXR

static inline void XR_RegisterCVars( void ) {}
static inline qboolean XR_Init( void ) { return false; }
static inline qboolean XR_InitGraphics( void ) { return false; }
static inline void XR_EnsureCurrent( void ) {}
static inline void* XR_GetGraphicsBinding( void ) { return NULL; }
static inline qboolean XR_CreateSession( void ) { return false; }
static inline qboolean XR_IsActive( void ) { return false; }
static inline qboolean XR_IsSessionRunning( void ) { return false; }
static inline qboolean XR_IsInitialized( void ) { return false; }
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
static inline void XR_ResetHeadOriginCalibration( void ) {}
static inline qboolean XR_GetHeadCenterTransform( vec3_t out_origin_offset, vec3_t out_angles ) { if( out_origin_offset ) VectorClear( out_origin_offset ); if( out_angles ) VectorClear( out_angles ); return false; }
static inline qboolean XR_GetHeadCenterTransformWithBasis( vec3_t out_origin_offset, vec3_t out_forward, vec3_t out_right, vec3_t out_up ) {
    if( out_origin_offset ) VectorClear( out_origin_offset );
    if( out_forward ) { out_forward[0] = 1.0f; out_forward[1] = 0.0f; out_forward[2] = 0.0f; }
    if( out_right ) { out_right[0] = 0.0f; out_right[1] = -1.0f; out_right[2] = 0.0f; }
    if( out_up ) { out_up[0] = 0.0f; out_up[1] = 0.0f; out_up[2] = 1.0f; }
    return false;
}

#endif // XASH_OPENXR

#endif // XR_CORE_H
