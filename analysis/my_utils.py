
colors_impl_mapping = {
    "mpquic": "#E69F00",
    "mcmpquic": "#56B4E9",
    "quic": "#009E73",
    "mcmpquic-aff": "#F0E442",
    "mcmpquic-rfs": "#CC79A7",
}

def get_color_for_impl(impl: str):
    return colors_impl_mapping.get(impl, "black")