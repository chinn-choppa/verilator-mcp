// An intentionally failing self-checking test; Apache-2.0.
module tb_fatal;
    initial begin
        #1;
        $fatal(1, "INTENTIONAL_VERIFICATION_FAILURE");
    end
endmodule
