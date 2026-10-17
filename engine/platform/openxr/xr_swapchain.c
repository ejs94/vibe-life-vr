#include "common.h"
#include "xr_swapchain.h"
#include "xr_input.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifdef XASH_OPENXR

#if !defined(__ANDROID__)
#define XR_USE_PLATFORM_XLIB
#define XR_USE_GRAPHICS_API_OPENGL
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <GL/glx.h>
#include <GL/gl.h>
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>
#else
#define XR_USE_PLATFORM_ANDROID
#define XR_USE_GRAPHICS_API_OPENGL_ES
#include <jni.h>
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>
#endif

xr_eye_swapchain_t g_xrEyeSwapchains[2];
XrView g_xrViews[2];
qboolean g_xrSwapchainsReady = false;
static XrFrameState g_currentFrameState;

qboolean XR_CreateSwapchains( void )
{
    if (g_xrEyeSwapchains[0].swapchain != XR_NULL_HANDLE)
    {
        return true;
    }

    if (g_xrSession == XR_NULL_HANDLE)
    {
        Con_Printf("XR_CreateSwapchains: Invalid XrSession!\n");
        return false;
    }

    XR_EnsureCurrent();

    Con_Printf("XR_CreateSwapchains: Configuring stereo swapchains...\n");

    // 1. Enumerate supported swapchain formats
    uint32_t formatCount = 0;
    if (XR_FAILED(xrEnumerateSwapchainFormats(g_xrSession, 0, &formatCount, NULL)) || formatCount == 0)
    {
        Con_Printf("XR_CreateSwapchains: Failed to enumerate swapchain formats!\n");
        return false;
    }

    int64_t *formats = (int64_t*)malloc(sizeof(int64_t) * formatCount);
    xrEnumerateSwapchainFormats(g_xrSession, formatCount, &formatCount, formats);

    Con_Printf("XR_CreateSwapchains: Supported runtime swapchain formats (%u):\n", formatCount);
    for (uint32_t i = 0; i < formatCount; i++)
    {
        Con_Printf("  Format [%u]: 0x%llx\n", i, (unsigned long long)formats[i]);
    }

    int64_t selectedFormat = formats[0]; // fallback
    for (uint32_t i = 0; i < formatCount; i++)
    {
        if (formats[i] == GL_RGBA8)
        {
            selectedFormat = formats[i];
            break;
        }
    }
    Con_Printf("XR_CreateSwapchains: Selected format: 0x%llx\n", (unsigned long long)selectedFormat);
    free(formats);

    // 2. Query recommended eye resolutions
    uint32_t viewCount = 0;
    xrEnumerateViewConfigurationViews(g_xrInstance, g_xrSystemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0, &viewCount, NULL);
    if (viewCount != 2)
    {
        Con_Printf("XR_CreateSwapchains: Expected 2 views for stereo, got %d!\n", viewCount);
        return false;
    }

    XrViewConfigurationView configViews[2];
    for (int i = 0; i < 2; i++)
    {
        configViews[i].type = XR_TYPE_VIEW_CONFIGURATION_VIEW;
        configViews[i].next = NULL;
    }
    xrEnumerateViewConfigurationViews(g_xrInstance, g_xrSystemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 2, &viewCount, configViews);

    // 3. Create swapchain for each eye
    for (int eye = 0; eye < 2; eye++)
    {
        g_xrEyeSwapchains[eye].width = (configViews[eye].recommendedImageRectWidth + 3) & ~3;
        g_xrEyeSwapchains[eye].height = (configViews[eye].recommendedImageRectHeight + 3) & ~3;

        XrSwapchainCreateInfo createInfo = {0};
        createInfo.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
        createInfo.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT | XR_SWAPCHAIN_USAGE_TRANSFER_SRC_BIT | XR_SWAPCHAIN_USAGE_SAMPLED_BIT;
        createInfo.format = selectedFormat;
        createInfo.sampleCount = 1;
        createInfo.width = g_xrEyeSwapchains[eye].width;
        createInfo.height = g_xrEyeSwapchains[eye].height;
        createInfo.faceCount = 1;
        createInfo.arraySize = 1;
        createInfo.mipCount = 1;

        Con_Printf("XR_CreateSwapchains: Eye %d createInfo: w=%u h=%u format=0x%llx usage=0x%llx\n",
            eye, createInfo.width, createInfo.height, (unsigned long long)createInfo.format, (unsigned long long)createInfo.usageFlags);

        XrResult res = xrCreateSwapchain(g_xrSession, &createInfo, &g_xrEyeSwapchains[eye].swapchain);
        if (XR_FAILED(res))
        {
            Con_Printf("XR_CreateSwapchains: Eye %d create with TRANSFER_SRC failed (res = %d), retrying with COLOR_ATTACHMENT_BIT only...\n", eye, res);
            createInfo.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT;
            res = xrCreateSwapchain(g_xrSession, &createInfo, &g_xrEyeSwapchains[eye].swapchain);
        }
        if (XR_FAILED(res))
        {
            Con_Printf("XR_CreateSwapchains: Failed to create swapchain for eye %d (res = %d)\n", eye, res);
            return false;
        }

        // 4. Enumerate swapchain images
        uint32_t imageCount = 0;
        xrEnumerateSwapchainImages(g_xrEyeSwapchains[eye].swapchain, 0, &imageCount, NULL);
        g_xrEyeSwapchains[eye].imageCount = imageCount;

#if !defined(__ANDROID__)
        XrSwapchainImageOpenGLKHR *xrImages = (XrSwapchainImageOpenGLKHR*)malloc(sizeof(XrSwapchainImageOpenGLKHR) * imageCount);
        for (uint32_t j = 0; j < imageCount; j++)
        {
            xrImages[j].type = XR_TYPE_SWAPCHAIN_IMAGE_OPENGL_KHR;
            xrImages[j].next = NULL;
        }

        xrEnumerateSwapchainImages(g_xrEyeSwapchains[eye].swapchain, imageCount, &imageCount, (XrSwapchainImageBaseHeader*)xrImages);

        g_xrEyeSwapchains[eye].images = (uint32_t*)malloc(sizeof(uint32_t) * imageCount);
        for (uint32_t j = 0; j < imageCount; j++)
        {
            g_xrEyeSwapchains[eye].images[j] = xrImages[j].image;
        }
        free(xrImages);
#else
        XrSwapchainImageOpenGLESKHR *xrImages = (XrSwapchainImageOpenGLESKHR*)malloc(sizeof(XrSwapchainImageOpenGLESKHR) * imageCount);
        for (uint32_t j = 0; j < imageCount; j++)
        {
            xrImages[j].type = XR_TYPE_SWAPCHAIN_IMAGE_OPENGL_ES_KHR;
            xrImages[j].next = NULL;
        }

        xrEnumerateSwapchainImages(g_xrEyeSwapchains[eye].swapchain, imageCount, &imageCount, (XrSwapchainImageBaseHeader*)xrImages);

        g_xrEyeSwapchains[eye].images = (uint32_t*)malloc(sizeof(uint32_t) * imageCount);
        for (uint32_t j = 0; j < imageCount; j++)
        {
            g_xrEyeSwapchains[eye].images[j] = xrImages[j].image;
        }
        free(xrImages);
#endif

        Con_Printf("XR_CreateSwapchains: Eye %d configured! Resolution: %dx%d, Buffers: %d\n",
            eye, g_xrEyeSwapchains[eye].width, g_xrEyeSwapchains[eye].height, imageCount);
    }

    for (int i = 0; i < 2; i++)
    {
        g_xrViews[i].type = XR_TYPE_VIEW;
        g_xrViews[i].next = NULL;
    }

    g_xrSwapchainsReady = true;
    Con_Printf("XR_CreateSwapchains: Stereo swapchains created successfully!\n");
    return true;
}

void XR_DestroySwapchains( void )
{
    g_xrSwapchainsReady = false;
    for (int eye = 0; eye < 2; eye++)
    {
        if (g_xrEyeSwapchains[eye].swapchain != XR_NULL_HANDLE)
        {
            xrDestroySwapchain(g_xrEyeSwapchains[eye].swapchain);
            g_xrEyeSwapchains[eye].swapchain = XR_NULL_HANDLE;
        }
        if (g_xrEyeSwapchains[eye].images)
        {
            free(g_xrEyeSwapchains[eye].images);
            g_xrEyeSwapchains[eye].images = NULL;
        }
        g_xrEyeSwapchains[eye].imageCount = 0;
    }
}

qboolean XR_WaitFrame( XrFrameState *outFrameState )
{
    if (!g_xrSessionRunning) return false;

    XrFrameWaitInfo waitInfo = {0};
    waitInfo.type = XR_TYPE_FRAME_WAIT_INFO;

    memset(&g_currentFrameState, 0, sizeof(g_currentFrameState));
    g_currentFrameState.type = XR_TYPE_FRAME_STATE;

    XrResult res = xrWaitFrame(g_xrSession, &waitInfo, &g_currentFrameState);
    if (XR_FAILED(res)) return false;

    if (g_xrLocalSpace != XR_NULL_HANDLE)
    {
        XrViewLocateInfo locateInfo = {0};
        locateInfo.type = XR_TYPE_VIEW_LOCATE_INFO;
        locateInfo.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
        locateInfo.displayTime = g_currentFrameState.predictedDisplayTime;
        locateInfo.space = g_xrLocalSpace;

        XrViewState viewState = {0};
        viewState.type = XR_TYPE_VIEW_STATE;

        uint32_t viewCount = 2;
        xrLocateViews(g_xrSession, &locateInfo, &viewState, 2, &viewCount, g_xrViews);

        // Simulated head orientation for headless / automated regression testing
        if (vr_test_head && vr_test_head->value > 0.0f)
        {
            float p = (vr_test_head_pitch ? vr_test_head_pitch->value : 0.0f) * (3.14159265f / 180.0f);
            float y = (vr_test_head_yaw   ? vr_test_head_yaw->value   : 0.0f) * (3.14159265f / 180.0f);
            float r = (vr_test_head_roll  ? vr_test_head_roll->value  : 0.0f) * (3.14159265f / 180.0f);

            // OpenXR Euler mapping: Pitch around +X, Yaw around +Y, Roll around -Z
            float cp = cosf(p * 0.5f), sp = sinf(p * 0.5f);
            float cy = cosf(y * 0.5f), sy = sinf(y * 0.5f);
            float cr = cosf(-r * 0.5f), sr = sinf(-r * 0.5f);

            XrQuaternionf q;
            q.w = cy * cp * cr - sy * sp * sr;
            q.x = cy * sp * cr + sy * cp * sr;
            q.y = sy * cp * cr - cy * sp * sr;
            q.z = cy * cp * sr + sy * sp * cr;

            for (int eye = 0; eye < 2; eye++)
            {
                g_xrViews[eye].pose.orientation = q;
                g_xrViews[eye].pose.position.x = (eye == 0) ? -0.032f : 0.032f;
                g_xrViews[eye].pose.position.y = 1.65f;
                g_xrViews[eye].pose.position.z = 0.0f;
            }
        }
    }

    if (outFrameState)
    {
        *outFrameState = g_currentFrameState;
    }
    return true;
}


qboolean XR_BeginFrame( void )
{
    if (!g_xrSessionRunning) return false;

    XrFrameBeginInfo beginInfo = {0};
    beginInfo.type = XR_TYPE_FRAME_BEGIN_INFO;

    XrResult res = xrBeginFrame(g_xrSession, &beginInfo);
    return XR_SUCCEEDED(res);
}

static qboolean g_xrEyesAcquired = false;

void XR_BeginEye( int eye )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady || eye < 0 || eye > 1) return;

    XrSwapchainImageAcquireInfo acquireInfo = {0};
    acquireInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO;

    uint32_t imageIndex = 0;
    xrAcquireSwapchainImage(g_xrEyeSwapchains[eye].swapchain, &acquireInfo, &imageIndex);

    XrSwapchainImageWaitInfo waitInfo = {0};
    waitInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO;
    waitInfo.timeout = XR_INFINITE_DURATION;

    xrWaitSwapchainImage(g_xrEyeSwapchains[eye].swapchain, &waitInfo);
    g_xrEyeSwapchains[eye].currentImageIndex = imageIndex;
    g_xrEyesAcquired = true;
}

void XR_EndEye( int eye )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady || eye < 0 || eye > 1) return;

    // Issue #4: Khronos OpenXR Specification §10.3 requires all graphics commands
    // affecting the swapchain image to be committed before calling xrReleaseSwapchainImage.
    // In asynchronous GL/GLES drivers (e.g. GL4ES on Quest), glFlush() ensures commands
    // are dispatched to the GPU immediately.
    typedef void (*pfn_glFlush_t)(void);
    static pfn_glFlush_t s_glFlush = NULL;
    static qboolean s_glFlushResolved = false;
    if( !s_glFlushResolved )
    {
        s_glFlush = (pfn_glFlush_t)GL_GetProcAddress("glFlush");
        s_glFlushResolved = true;
    }
    if( s_glFlush )
        s_glFlush();

    XrSwapchainImageReleaseInfo releaseInfo = {0};
    releaseInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;

    xrReleaseSwapchainImage(g_xrEyeSwapchains[eye].swapchain, &releaseInfo);
}

static qboolean g_quadHudEnabled = false;

void XR_EndFrame( void )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady) return;

    // Khronos OpenXR Specification §10.1: Maintain continuous frame loop pacing.
    // If runtime signals shouldRender == XR_FALSE (e.g. headset in standby or system dialog active)
    // or if swapchain buffers were not acquired for this frame, submit xrEndFrame with layerCount = 0.
    if (!g_currentFrameState.shouldRender || !g_xrEyesAcquired)
    {
        XrFrameEndInfo endInfo = {0};
        endInfo.type = XR_TYPE_FRAME_END_INFO;
        endInfo.displayTime = g_currentFrameState.predictedDisplayTime;
        endInfo.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
        endInfo.layerCount = 0;
        endInfo.layers = NULL;

        xrEndFrame(g_xrSession, &endInfo);
        g_xrEyesAcquired = false;
        return;
    }

    // Locate eye views at predicted display time
    XrViewLocateInfo locateInfo = {0};
    locateInfo.type = XR_TYPE_VIEW_LOCATE_INFO;
    locateInfo.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
    locateInfo.displayTime = g_currentFrameState.predictedDisplayTime;
    locateInfo.space = g_xrLocalSpace;

    XrViewState viewState = {0};
    viewState.type = XR_TYPE_VIEW_STATE;

    uint32_t viewCount = 2;
    xrLocateViews(g_xrSession, &locateInfo, &viewState, 2, &viewCount, g_xrViews);

    // Prepare stereo projection layers
    XrCompositionLayerProjectionView projViews[2];
    for (int eye = 0; eye < 2; eye++)
    {
        projViews[eye].type = XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW;
        projViews[eye].next = NULL;
        projViews[eye].pose = g_xrViews[eye].pose;
        projViews[eye].fov = g_xrViews[eye].fov;
        projViews[eye].subImage.swapchain = g_xrEyeSwapchains[eye].swapchain;
        projViews[eye].subImage.imageRect.offset.x = 0;
        projViews[eye].subImage.imageRect.offset.y = 0;
        projViews[eye].subImage.imageRect.extent.width = g_xrEyeSwapchains[eye].width;
        projViews[eye].subImage.imageRect.extent.height = g_xrEyeSwapchains[eye].height;
        projViews[eye].subImage.imageArrayIndex = 0;
    }

    XrCompositionLayerProjection projLayer = {0};
    projLayer.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION;
    projLayer.layerFlags = 0;
    projLayer.space = g_xrLocalSpace;
    projLayer.viewCount = 2;
    projLayer.views = projViews;

    XrCompositionLayerQuad quadLayer = {0};
    quadLayer.type = XR_TYPE_COMPOSITION_LAYER_QUAD;
    quadLayer.layerFlags = XR_COMPOSITION_LAYER_BLEND_TEXTURE_SOURCE_ALPHA_BIT;
    quadLayer.space = (g_xrViewSpace != XR_NULL_HANDLE) ? g_xrViewSpace : g_xrLocalSpace;
    quadLayer.subImage.swapchain = g_xrEyeSwapchains[0].swapchain;
    quadLayer.subImage.imageRect.offset.x = 0;
    quadLayer.subImage.imageRect.offset.y = 0;
    quadLayer.subImage.imageRect.extent.width = g_xrEyeSwapchains[0].width;
    quadLayer.subImage.imageRect.extent.height = g_xrEyeSwapchains[0].height;
    quadLayer.pose.position.x = 0.0f;
    quadLayer.pose.position.y = 0.0f;
    quadLayer.pose.position.z = -1.5f; // Floating 1.5m ahead
    quadLayer.pose.orientation.w = 1.0f;
    quadLayer.size.width = 1.6f;
    quadLayer.size.height = 0.9f;

    const XrCompositionLayerBaseHeader *layers[2];
    uint32_t activeLayers = 0;

    layers[activeLayers++] = (const XrCompositionLayerBaseHeader*)&projLayer;
    g_xrEyesAcquired = false;

    if (g_quadHudEnabled)
    {
        layers[activeLayers++] = (const XrCompositionLayerBaseHeader*)&quadLayer;
    }

    XrFrameEndInfo endInfo = {0};
    endInfo.type = XR_TYPE_FRAME_END_INFO;
    endInfo.displayTime = g_currentFrameState.predictedDisplayTime;
    endInfo.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
    endInfo.layerCount = activeLayers;
    endInfo.layers = (activeLayers > 0) ? layers : NULL;

    xrEndFrame(g_xrSession, &endInfo);
}

EXPORT void XR_EndMenuFrame( void )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady) return;

    if (!g_currentFrameState.shouldRender || !g_xrEyesAcquired)
    {
        XrFrameEndInfo endInfo = {0};
        endInfo.type = XR_TYPE_FRAME_END_INFO;
        endInfo.displayTime = g_currentFrameState.predictedDisplayTime;
        endInfo.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
        endInfo.layerCount = 0;
        endInfo.layers = NULL;

        xrEndFrame(g_xrSession, &endInfo);
        g_xrEyesAcquired = false;
        return;
    }

    // Build quad layer displaying Eye 0 swapchain to both eyes in VR space.
    // Floating comfortably 1.5m in front of the headset origin in VIEW space (Issue #2).
    // Pattern inspired by Team Beef (Lambda1VR TBXR_submitFrame quad layer).
    XrCompositionLayerQuad quadLayer = {0};
    quadLayer.type = XR_TYPE_COMPOSITION_LAYER_QUAD;
    quadLayer.layerFlags = XR_COMPOSITION_LAYER_BLEND_TEXTURE_SOURCE_ALPHA_BIT;
    quadLayer.space = (g_xrViewSpace != XR_NULL_HANDLE) ? g_xrViewSpace : g_xrLocalSpace;
    quadLayer.eyeVisibility = XR_EYE_VISIBILITY_BOTH;
    quadLayer.subImage.swapchain = g_xrEyeSwapchains[0].swapchain;
    quadLayer.subImage.imageRect.offset.x = 0;
    quadLayer.subImage.imageRect.offset.y = 0;
    quadLayer.subImage.imageRect.extent.width = g_xrEyeSwapchains[0].width;
    quadLayer.subImage.imageRect.extent.height = g_xrEyeSwapchains[0].height;
    quadLayer.subImage.imageArrayIndex = 0;
    float menuDist = (vr_menu_distance && vr_menu_distance->value > 0.5f) ? vr_menu_distance->value : 2.1f;
    float menuScale = (vr_menu_scale && vr_menu_scale->value > 0.5f) ? vr_menu_scale->value : 1.8f;

    quadLayer.pose.position.x = 0.0f;
    quadLayer.pose.position.y = 0.0f;
    quadLayer.pose.position.z = -menuDist;
    quadLayer.pose.orientation.w = 1.0f;
    quadLayer.size.width = menuScale;
    quadLayer.size.height = menuScale * ((float)g_xrEyeSwapchains[0].height / (float)g_xrEyeSwapchains[0].width);

    const XrCompositionLayerBaseHeader *layers[1];
    layers[0] = (const XrCompositionLayerBaseHeader*)&quadLayer;

    XrFrameEndInfo endInfo = {0};
    endInfo.type = XR_TYPE_FRAME_END_INFO;
    endInfo.displayTime = g_currentFrameState.predictedDisplayTime;
    endInfo.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
    endInfo.layerCount = 1;
    endInfo.layers = layers;

    xrEndFrame(g_xrSession, &endInfo);
    g_xrEyesAcquired = false;
}

EXPORT void XR_RunMenuFrame( void )
{
    if (!g_xrSessionRunning) return;

    XR_WaitFrame( NULL );
    XR_BeginFrame();
    XR_EndMenuFrame();
}

qboolean XR_IsQuadHudActive( void )
{
    return g_quadHudEnabled;
}

void XR_SetQuadHud( qboolean enabled )
{
    g_quadHudEnabled = enabled;
}

XrTime XR_GetPredictedDisplayTime( void )
{
    return g_currentFrameState.predictedDisplayTime;
}

void XR_QuatToEuler( const XrQuaternionf *q, vec3_t out_angles )
{
    float sp = 2.0f * (q->y * q->z - q->x * q->w);
    float pitch;
    float yaw;
    float roll;

    if (fabsf(sp) >= 1.0f)
    {
        pitch = copysignf((float)M_PI / 2.0f, sp);
        yaw = atan2f(-2.0f * (q->x * q->y - q->z * q->w), 1.0f - 2.0f * (q->y * q->y + q->z * q->z));
        roll = 0.0f;
    }
    else
    {
        pitch = asinf(sp);
        yaw = atan2f(2.0f * (q->x * q->z + q->y * q->w), 1.0f - 2.0f * (q->x * q->x + q->y * q->y));
        roll = atan2f(2.0f * (q->x * q->y + q->z * q->w), 1.0f - 2.0f * (q->x * q->x + q->z * q->z));
    }

    out_angles[0] = pitch * (180.0f / (float)M_PI);
    out_angles[1] = yaw * (180.0f / (float)M_PI);
    out_angles[2] = roll * (180.0f / (float)M_PI);
}

void XR_GetHeadOrientation( vec3_t out_angles )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady)
    {
        out_angles[0] = 0.0f;
        out_angles[1] = 0.0f;
        out_angles[2] = 0.0f;
        return;
    }

    XR_QuatToEuler( &g_xrViews[0].pose.orientation, out_angles );
}

void XR_GetEyePosition( int eye, vec3_t out_origin )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady || eye < 0 || eye > 1)
    {
        out_origin[0] = 0.0f;
        out_origin[1] = 0.0f;
        out_origin[2] = 0.0f;
        return;
    }

    // OpenXR coordinates: +X = Right, +Y = Up, +Z = Back (-Z = Forward)
    // GoldSrc coordinates: +X = Forward (-Z), +Y = Left (-X), +Z = Up (+Y)
    out_origin[0] = -g_xrViews[eye].pose.position.z;
    out_origin[1] = -g_xrViews[eye].pose.position.x;
    out_origin[2] = g_xrViews[eye].pose.position.y;
}

void XR_GetEyeFrustum( int eye, float nearZ, float farZ, float *left, float *right, float *bottom, float *top )
{
    if (!left || !right || !bottom || !top) return;

    if (!g_xrSessionRunning || !g_xrSwapchainsReady || eye < 0 || eye > 1 ||
        g_xrViews[eye].fov.angleRight <= g_xrViews[eye].fov.angleLeft)
    {
        *left = *right = *bottom = *top = 0.0f;
        return;
    }

    *left   = tanf(g_xrViews[eye].fov.angleLeft) * nearZ;
    *right  = tanf(g_xrViews[eye].fov.angleRight) * nearZ;
    *bottom = tanf(g_xrViews[eye].fov.angleDown) * nearZ;
    *top    = tanf(g_xrViews[eye].fov.angleUp) * nearZ;
}

static vec3_t s_vrHeadBaseOrigin = {0.0f, 1.65f, 0.0f};
static qboolean s_vrHeadOriginCalibrated = false;

/*
=================
XR_ResetHeadOriginCalibration

Resets baseline head origin calibration for roomscale centering.
=================
*/
void XR_ResetHeadOriginCalibration( void )
{
    s_vrHeadOriginCalibrated = false;
    VectorSet( s_vrHeadBaseOrigin, 0.0f, 1.65f, 0.0f );
}

/*
=================
XR_GetHeadCenterTransform

Calculates the 6DoF midpoint between the player's physical eyes, rotated by
locomotion turning yaw and scaled to GoldSrc world units.
Used by the 3D spatial audio listener and camera positioning.
=================
*/
qboolean XR_GetHeadCenterTransform( vec3_t out_origin_offset, vec3_t out_angles )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady)
        return false;

    // Head center in OpenXR space: midpoint between left and right eye tracking poses
    float head_x = (g_xrViews[0].pose.position.x + g_xrViews[1].pose.position.x) * 0.5f;
    float head_y = (g_xrViews[0].pose.position.y + g_xrViews[1].pose.position.y) * 0.5f;
    float head_z = (g_xrViews[0].pose.position.z + g_xrViews[1].pose.position.z) * 0.5f;

    // Calibrate baseline head position when first non-zero tracking data arrives
    if (!s_vrHeadOriginCalibrated && (fabsf(head_x) > 0.001f ||
                                      fabsf(head_y) > 0.001f ||
                                      fabsf(head_z) > 0.001f))
    {
        s_vrHeadBaseOrigin[0] = head_x;
        s_vrHeadBaseOrigin[1] = head_y;
        s_vrHeadBaseOrigin[2] = head_z;
        s_vrHeadOriginCalibrated = true;
    }

    float worldscale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
    float turn_yaw = XR_GetPlayerTurnYaw();
    float yaw_rad = turn_yaw * (3.14159265f / 180.0f);
    float cy = cosf( yaw_rad );
    float sy = sinf( yaw_rad );

    // OpenXR room coordinates relative to calibrated player origin:
    // +X = Right, +Y = Up, -Z = Forward
    float room_forward = -(head_z - s_vrHeadBaseOrigin[2]);
    float room_right   =  (head_x - s_vrHeadBaseOrigin[0]);
    float room_up      =  (head_y - s_vrHeadBaseOrigin[1]);

    if (vr_height_adjust)
        room_up += vr_height_adjust->value / worldscale;

    // Rotate room displacement by player locomotion turning yaw into GoldSrc world coordinates:
    if (out_origin_offset)
    {
        out_origin_offset[0] = (room_forward * cy + room_right * sy) * worldscale;
        out_origin_offset[1] = (room_forward * sy - room_right * cy) * worldscale;
        out_origin_offset[2] = room_up * worldscale;
    }

    // Extract orientation from eye 0 quaternion (representing head pose orientation)
    if (out_angles)
    {
        XR_QuatToEuler( &g_xrViews[0].pose.orientation, out_angles );
        out_angles[1] = anglemod( out_angles[1] + turn_yaw );
    }

    return true;
}

/*
=================
XR_GetHeadCenterTransformWithBasis

Calculates 6DoF head midpoint and exact listener basis vectors (forward, right, up)
in GoldSrc coordinates directly from OpenXR orientation quaternion and locomotion turn yaw.
Avoids Euler gimbal lock and aligns 100% with renderer frustum.
=================
*/
qboolean XR_GetHeadCenterTransformWithBasis( vec3_t out_origin_offset, vec3_t out_forward, vec3_t out_right, vec3_t out_up )
{
    if (!g_xrSessionRunning || !g_xrSwapchainsReady)
        return false;

    // Head center in OpenXR space: midpoint between left and right eye tracking poses
    float head_x = (g_xrViews[0].pose.position.x + g_xrViews[1].pose.position.x) * 0.5f;
    float head_y = (g_xrViews[0].pose.position.y + g_xrViews[1].pose.position.y) * 0.5f;
    float head_z = (g_xrViews[0].pose.position.z + g_xrViews[1].pose.position.z) * 0.5f;

    // Calibrate baseline head position when first non-zero tracking data arrives
    if (!s_vrHeadOriginCalibrated && (fabsf(head_x) > 0.001f ||
                                      fabsf(head_y) > 0.001f ||
                                      fabsf(head_z) > 0.001f))
    {
        s_vrHeadBaseOrigin[0] = head_x;
        s_vrHeadBaseOrigin[1] = head_y;
        s_vrHeadBaseOrigin[2] = head_z;
        s_vrHeadOriginCalibrated = true;
    }

    float worldscale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
    float turn_yaw = XR_GetPlayerTurnYaw();
    float yaw_rad = turn_yaw * (3.14159265f / 180.0f);
    float cy = cosf( yaw_rad );
    float sy = sinf( yaw_rad );

    // OpenXR room coordinates relative to calibrated player origin:
    // +X = Right, +Y = Up, -Z = Forward
    float room_forward = -(head_z - s_vrHeadBaseOrigin[2]);
    float room_right   =  (head_x - s_vrHeadBaseOrigin[0]);
    float room_up      =  (head_y - s_vrHeadBaseOrigin[1]);

    if (vr_height_adjust)
        room_up += vr_height_adjust->value / worldscale;

    // Rotate room displacement by player locomotion turning yaw into GoldSrc world coordinates:
    if (out_origin_offset)
    {
        out_origin_offset[0] = (room_forward * cy + room_right * sy) * worldscale;
        out_origin_offset[1] = (room_forward * sy - room_right * cy) * worldscale;
        out_origin_offset[2] = room_up * worldscale;
    }

    // Direct basis vector derivation from OpenXR orientation quaternion (matching R_SetupFrustum):
    const XrQuaternionf *q = &g_xrViews[0].pose.orientation;
    float qx = q->x, qy = q->y, qz = q->z, qw = q->w;

    vec3_t rxr, uxr, fxr;
    rxr[0] = 1.0f - 2.0f * (qy * qy + qz * qz);
    rxr[1] = 2.0f * (qx * qy + qz * qw);
    rxr[2] = 2.0f * (qx * qz - qy * qw);

    uxr[0] = 2.0f * (qx * qy - qz * qw);
    uxr[1] = 1.0f - 2.0f * (qx * qx + qz * qz);
    uxr[2] = 2.0f * (qy * qz + qx * qw);

    fxr[0] = -2.0f * (qx * qz + qy * qw);
    fxr[1] = -2.0f * (qy * qz - qx * qw);
    fxr[2] = -(1.0f - 2.0f * (qx * qx + qy * qy));

    if (out_forward)
    {
        out_forward[0] = (-fxr[2]) * cy + fxr[0] * sy;
        out_forward[1] = (-fxr[2]) * sy - fxr[0] * cy;
        out_forward[2] = fxr[1];
        VectorNormalize( out_forward );
    }

    if (out_right)
    {
        out_right[0] = (-rxr[2]) * cy + rxr[0] * sy;
        out_right[1] = (-rxr[2]) * sy - rxr[0] * cy;
        out_right[2] = rxr[1];
        VectorNormalize( out_right );
    }

    if (out_up)
    {
        out_up[0] = (-uxr[2]) * cy + uxr[0] * sy;
        out_up[1] = (-uxr[2]) * sy - uxr[0] * cy;
        out_up[2] = uxr[1];
        VectorNormalize( out_up );
    }

    return true;
}

#endif // XASH_OPENXR

