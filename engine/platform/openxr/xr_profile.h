#ifndef XR_PROFILE_H
#define XR_PROFILE_H

#include "xr_core.h"

#ifdef XASH_OPENXR

#define MAX_VR_WEAPON_PROFILES 128

// Declarative VR weapon profile calibration structure
typedef struct vr_weapon_profile_s
{
    char    model_name[64];              // e.g. "v_9mmhandgun.mdl" or "v_shotgun.mdl"
    char    display_name[64];            // e.g. "Glock 17 (9mm Handgun)"
    char    type[32];                    // "hitscan", "melee", "projectile", "beam", "toss", "placeable", "tool", "hand"
    int     muzzle_attachment;           // Primary muzzle flash/laser attachment index (-1 if none)
    vec3_t  muzzle_fallback;             // Local offset fallback [fwd, right, up] if attachment missing
    int     ejection_attachment;         // Spent casing ejection attachment index (-1 if none)
    int     magwell_attachment;          // Magazine well attachment index (-1 if none)
    vec3_t  grip_offset;                 // Position offset [forward, right, up] in GoldSrc units
    float   pitch_adjust;                // Barrel pitch adjustment degrees
    float   yaw_adjust;                  // Barrel yaw adjustment degrees
    float   roll_adjust;                 // Barrel roll adjustment degrees
    qboolean two_handed;                 // Whether two-handed stabilization is permitted
    float   two_hand_min_dist;           // Minimum separation distance in meters
    float   two_hand_max_dist;           // Maximum separation distance in meters
    float   recoil_pitch;                // Procedural recoil pitch degrees
    float   haptic_fire_amplitude;       // Vibration intensity for primary fire (0.0 - 1.0)
    float   haptic_fire_duration_ms;     // Vibration duration in milliseconds
    float   haptic_impact_amplitude;     // Impact vibration intensity for melee/crowbar
    float   haptic_impact_duration_ms;   // Impact vibration duration in milliseconds
} vr_weapon_profile_t;

// Lifecycle and profile management
EXPORT void XR_InitWeaponProfiles( void );
EXPORT void XR_ReloadWeaponProfiles( void );
EXPORT int  XR_GetWeaponProfileCount( void );

// Profile lookup by model name (supports full path e.g. "models/v_crowbar.mdl" or basename)
EXPORT const vr_weapon_profile_t *XR_FindWeaponProfile( const char *model_name );

// Query calibration for currently held weapon model
EXPORT const vr_weapon_profile_t *XR_GetActiveWeaponProfile( void );

// Convenience query helpers
EXPORT void     XR_GetWeaponGripOffset( const char *model_name, vec3_t out_offset );
EXPORT void     XR_GetWeaponPitchAdjust( const char *model_name, float *out_pitch, float *out_yaw, float *out_roll );
EXPORT qboolean XR_GetWeaponTwoHandParams( const char *model_name, qboolean *out_twohanded, float *out_min_dist, float *out_max_dist );
EXPORT qboolean XR_GetWeaponMuzzleParams( const char *model_name, int *out_attachment, vec3_t out_fallback );
EXPORT qboolean XR_GetWeaponHaptics( const char *model_name, float *out_fire_amp, float *out_fire_dur );

#else // !XASH_OPENXR

typedef struct vr_weapon_profile_s
{
    char model_name[64];
} vr_weapon_profile_t;

static inline void XR_InitWeaponProfiles( void ) {}
static inline void XR_ReloadWeaponProfiles( void ) {}
static inline int  XR_GetWeaponProfileCount( void ) { return 0; }
static inline const vr_weapon_profile_t *XR_FindWeaponProfile( const char *model_name ) { return NULL; }
static inline const vr_weapon_profile_t *XR_GetActiveWeaponProfile( void ) { return NULL; }
static inline void XR_GetWeaponGripOffset( const char *model_name, vec3_t out_offset ) { if (out_offset) VectorClear(out_offset); }
static inline void XR_GetWeaponPitchAdjust( const char *model_name, float *out_pitch, float *out_yaw, float *out_roll ) {
    if (out_pitch) *out_pitch = 0.0f;
    if (out_yaw)   *out_yaw   = 0.0f;
    if (out_roll)  *out_roll  = 0.0f;
}
static inline qboolean XR_GetWeaponTwoHandParams( const char *model_name, qboolean *out_twohanded, float *out_min_dist, float *out_max_dist ) {
    if (out_twohanded) *out_twohanded = true;
    if (out_min_dist) *out_min_dist = 0.12f;
    if (out_max_dist) *out_max_dist = 0.55f;
    return false;
}
static inline qboolean XR_GetWeaponMuzzleParams( const char *model_name, int *out_attachment, vec3_t out_fallback ) {
    if (out_attachment) *out_attachment = 0;
    if (out_fallback) { out_fallback[0] = 0; out_fallback[1] = 18.0f; out_fallback[2] = 0; }
    return false;
}
static inline qboolean XR_GetWeaponHaptics( const char *model_name, float *out_fire_amp, float *out_fire_dur ) {
    if (out_fire_amp) *out_fire_amp = 0.8f;
    if (out_fire_dur) *out_fire_dur = 60.0f;
    return false;
}

#endif // XASH_OPENXR

#endif // XR_PROFILE_H
