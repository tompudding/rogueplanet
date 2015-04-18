#version 140
#extension GL_ARB_explicit_attrib_location : require
#extension GL_ARB_explicit_uniform_location : require

uniform sampler2D tex;
uniform int using_textures;
in vec2 texcoord;
in vec4 colour;

layout(location = 0) out vec4 out_colour;

void main()
{
    if(1 == using_textures) {
        out_colour = texture(tex, texcoord)*colour;
    }
    else {
        out_colour = colour;
    }
    if(out_colour.a == 0) {
        discard;
    }
}
