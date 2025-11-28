function formatSignature(o) {
    parts = o.split(':');
    
    if (parts[0] == 'failed') {
        /* We'll display that it has failed to retrace on the problem page.
         * There's not enough space here for that, plus developers will
         * know its a failed retrace by seeing shared objects instead of
         * function names */
        parts.shift();
    }
    
    binary = parts[0].replace(/[\s\S]*\//,'');
    signal = parts[1];
    formatted = binary + " (" + signal + ") " + parts.slice(2).join(' → ');
    formatted = formatted.replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return formatted;
} 
