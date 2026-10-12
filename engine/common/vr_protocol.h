/*
vr_protocol.h - Cross-Platform VR & Crossplay Protocol Specifications
Copyright (C) 2026 Xash3D FWGS VR Project

This header defines network flags, userinfo keys, and fallbacks for cross-platform
compatibility between VR clients (PCVR / Quest standalone) and Flat clients
(Android mobile / PC desktop), as well as compatibility with vanilla GoldSrc servers.
*/

#ifndef VR_PROTOCOL_H
#define VR_PROTOCOL_H

#ifdef __cplusplus
extern "C" {
#endif

/*
===============================================================================
VR USERINFO KEYS & NETWORK NEGOTIATION
===============================================================================
Standard GoldSrc/Xash3D engines use userinfo key-value strings for client settings.
Keys prefixed with '*' are engine-managed and cannot be altered by arbitrary scripts.
*/

// Userinfo key indicating client VR status ("0" = Flat, "1" = VR 6DoF, "2" = VR Seated/3DoF)
#define VR_USERINFO_KEY            "*cl_vr"

// Userinfo key indicating VR input/hand controller capabilities bitmask (hex string)
#define VR_USERINFO_CAPS           "*cl_vr_caps"

// Userinfo key indicating controller profile type (e.g., "quest_touch", "index", "vive", "flat")
#define VR_USERINFO_DEVICE         "*cl_vr_device"

/*
===============================================================================
VR CAPABILITY BITMASK FLAGS
===============================================================================
Used in *cl_vr_caps to declare client tracking fidelity to server addons.
*/
enum vr_capability_flags_e
{
	VR_CAP_NONE                  = 0,
	VR_CAP_ACTIVE                = (1 << 0), // VR runtime is currently rendering & tracking
	VR_CAP_6DOF_HEAD             = (1 << 1), // Full positional head tracking available
	VR_CAP_6DOF_CONTROLLERS      = (1 << 2), // Dual 6DoF motion controllers active
	VR_CAP_HAND_TRACKING         = (1 << 3), // Optical hand tracking without controllers
	VR_CAP_DECOUPLED_WEAPON_AIM  = (1 << 4), // Weapon aim is decoupled from view direction
	VR_CAP_OFFHAND_INTERACTION   = (1 << 5), // Off-hand two-handed grip / physical reload
	VR_CAP_HAPTIC_FEEDBACK       = (1 << 6), // Multi-channel tactile feedback supported
	VR_CAP_ROOMSCALE             = (1 << 7), // Physical roomscale movement enabled
	VR_CAP_LEFT_HANDED           = (1 << 8), // Dominant weapon hand is left
	VR_CAP_SEATED                = (1 << 9)  // Seated / accessibility mode
};

/*
===============================================================================
SERVER CROSSPLAY COMPATIBILITY MODES
===============================================================================
Controls how a server interacts with VR clients.
*/
enum vr_crossplay_mode_e
{
	// Mode 0 (Vanilla Fallback): Server does not know about VR.
	// VR client maps hand aim directly to usercmd_t->viewangles.
	// Server traces hitscans and projectiles from eye/gun viewangles as in vanilla GoldSrc.
	// 100% backward compatible with vanilla servers and unmodified HLDS.
	VR_CROSSPLAY_VANILLA_FALLBACK = 0,

	// Mode 1 (VR-Enhanced Crossplay): Server supports both Flat and VR clients.
	// VR clients send decoupled muzzle origin/angles via extended pev or userinfo.
	// Flat clients continue standard crosshair aiming.
	// Server renders VR players with distinct controller poses.
	VR_CROSSPLAY_ENHANCED_HYBRID  = 1,

	// Mode 2 (VR-Exclusive): Server requires VR clients (*cl_vr != 0).
	VR_CROSSPLAY_VR_ONLY          = 2
};

/*
===============================================================================
CUSTOM USER MESSAGES FOR VR ENHANCED SERVERS
===============================================================================
Optional network messages registered only when sv_vr_crossplay is enabled.
*/
#define VR_MSG_CONTROLLER_POSE     "VR_Pose"     // Broadcast other players' hand poses
#define VR_MSG_HAPTIC_EVENT        "VR_Haptic"   // Server triggers directional haptics
#define VR_MSG_GESTURE_EVENT       "VR_Gesture"  // Hand sign / gesture replication

#ifdef __cplusplus
}
#endif

#endif // VR_PROTOCOL_H
