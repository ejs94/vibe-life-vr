#include "common.h"
#include "xr_swapchain.h"
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
#if !defined(__ANDROID__)
        if (formats[i] == GL_RGBA8 || formats[i] == GL_SRGB8_ALPHA8_EXT)
#else
        if (formats[i] == GL_RGBA8)
#endif
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
        g_xrEyeSwapchains[eye].width = configViews[eye].recommendedImageRectWidth;
        g_xrEyeSwapchains[eye].height = configViews[eye].recommendedImageRectHeight;

        XrSwapchainCreateInfo createInfo = {0};
        createInfo.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
        createInfo.usageFlags = XR_SWAPCHAIN_USAGE_SAMPLED_BIT | XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT | XR_SWAPCHAIN_USAGE_TRANSFER_SRC_BIT;
        createInfo.format = selectedFormat;
        createInfo.sampleCount = 1;
        createInfo.width = g_xrEyeSwapchains[eye].width;
        createInfo.height = g_xrEyeSwapchains[eye].height;
        createInfo.faceCount = 1;
        createInfo.arraySize = 1;
        createInfo.mipCount = 1;

        XrResult res = xrCreateSwapchain(g_xrSession, &createInfo, &g_xrEyeSwapchains[eye].swapchain);
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
    quadLayer.space = g_xrLocalSpace;
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
    // Floating comfortably 1.5m in front of the headset origin.
    // Pattern inspired by Team Beef (Lambda1VR TBXR_submitFrame quad layer).
    XrCompositionLayerQuad quadLayer = {0};
    quadLayer.type = XR_TYPE_COMPOSITION_LAYER_QUAD;
    quadLayer.layerFlags = XR_COMPOSITION_LAYER_BLEND_TEXTURE_SOURCE_ALPHA_BIT;
    quadLayer.space = g_xrLocalSpace;
    quadLayer.eyeVisibility = XR_EYE_VISIBILITY_BOTH;
    quadLayer.subImage.swapchain = g_xrEyeSwapchains[0].swapchain;
    quadLayer.subImage.imageRect.offset.x = 0;
    quadLayer.subImage.imageRect.offset.y = 0;
    quadLayer.subImage.imageRect.extent.width = g_xrEyeSwapchains[0].width;
    quadLayer.subImage.imageRect.extent.height = g_xrEyeSwapchains[0].height;
    quadLayer.subImage.imageArrayIndex = 0;
    quadLayer.pose.position.x = 0.0f;
    quadLayer.pose.position.y = 0.0f;
    quadLayer.pose.position.z = -1.5f;
    quadLayer.pose.orientation.w = 1.0f;
    quadLayer.size.width = 1.8f;
    quadLayer.size.height = 1.8f * ((float)g_xrEyeSwapchains[0].height / (float)g_xrEyeSwapchains[0].width);

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


#endif // XASH_OPENXR
